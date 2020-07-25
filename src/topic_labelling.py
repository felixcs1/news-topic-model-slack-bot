import json
import logging
import os
import re
import string
from collections import defaultdict
from typing import Any, Dict, List, Tuple, Optional

import en_core_web_sm
import numpy as np
from gensim.corpora.dictionary import Dictionary
from gensim.models import Phrases
from gensim.models.wrappers import LdaMallet, ldamallet

import config

logger = logging.getLogger(__name__)
logger.setLevel(config.log_level)

nlp = en_core_web_sm.load()


def normalise_doc(doc: str) -> str:
    """Remove numbers, punctuation from text and make all words lower case."""

    logger.debug('Normalising document')
    punc = string.punctuation
    doc = doc.lower()
    cleaned_tokens = [re.sub(r'([^a-zA-Z ]+?)', '', re.sub(f'([\d\s{punc} ]+?)', '', token)) for token in doc.split()]

    return ' '.join(list(filter(None, cleaned_tokens)))


def spacy_process(doc: str) -> str:
    """Use spacy en_core_web_sm model to remove stop words, lemmatise and remove POS."""

    logger.debug('Spacy processing')
    # Add custom stopword(s) to the spacy model
    custom_stop_words = {'coronavirus'}
    nlp.Defaults.stop_words |= custom_stop_words

    spacy_doc = nlp(doc)

    return ' '.join([token.lemma_ for token in spacy_doc if not token.is_stop])


def compute_ngrams(doc: str) -> str:
    """Load in pre-trained ngram model and apply to article to recover ngrams."""

    logger.debug('Computing N-Grams')
    ngram_model = Phrases.load(os.path.join(config.local_model_path, 'ngram_model.pkl'))

    tokens_with_ngrams = ngram_model[doc.split(" ")]

    return " ".join(tokens_with_ngrams)


def preprocess_document(doc: str) -> List[str]:
    """Apply preprocessing functions to document."""

    logger.debug('Preprocessing article...')
    normalised = normalise_doc(doc)
    spacy_processed = spacy_process(normalised)
    ngram_computed = compute_ngrams(spacy_processed)

    return ngram_computed.split(" ")


def get_topic_vector(preprocessed_doc: List[str]) -> List[Tuple[int, float]]:
    """Take in a preprocessed document, covert to bag of words, apply the topic model
    and return the topic distribution.

    Args:
        preprocessed_doc: Document as list of preprocessed words, e.g. ['article', 'important', 'word'...]

    Returns:
        Topic distribution as list of tuples of (int, float), representing (topic_number, topic_percentage), e.g.
        [(0, 0.014330332), (1, 0.22703473), (4, 0.057342175), (8, 0.021801356)...]
    """

    logger.debug('Loading Gensim dictionary')
    gensim_dictionary = Dictionary.load(os.path.join(config.local_model_path, 'gensim_dictionary'))

    logger.debug('Converting preprocessed article to bag of words')
    article_bow = gensim_dictionary.doc2bow(preprocessed_doc)

    logger.debug('Loading LDA MALLET model')
    lda_model_unconverted = LdaMallet.load(os.path.join(config.local_model_path, 'lda_model_mallet.model'))
    lda_model = ldamallet.malletmodel2ldamodel(lda_model_unconverted)

    np.random.seed(100)
    logger.debug('Producing topic vector')
    topic_vector = lda_model[article_bow]

    logger.debug(f'Got topic vector: {topic_vector}')
    return topic_vector


def topic_labels_from_vector(topic_vector: List[Tuple[str, float]]) -> Optional[List[Dict[str, Any]]]:
    """Assigns topic labels from given topic vector.

    The number of topics assigned is decided by the rule:

    "For an article, as many topics as it takes to surpass the given high threshold, but a maximum of 3 topics,
    with each topic surpassing a given low threshold of the article."

    If no topics are above the low threshold, then returns 'Other articles'.

    Args:
        topic_vector: In form [('Arts/Culture', 0.014330332), ('Scotland', 0.22703473), ('Education', 0.057342175)...]

    Returns:
        List of 1-3 dicts of {str: str, str: float} representing
        {'name': <human-readable topic label>, 'score': <percentage topic weight>}),
        e.g. [{'name': 'Arts/Culture', 'score': 0.2270347}, {'name': 'Scotland', 'score': 0.514330}],
        or [{'name': 'Other articles', 'score': 0.99}] if no topics are above the weight threshold.
    """

    low_threshold = config.topic_score_threshold_low
    high_threshold =  config.topic_score_threshold_high

    # Take top three topics
    top_three_topics: List[Tuple[str, np.float32]] = sorted(topic_vector, key=lambda x: x[1], reverse=True)[:3]

    # Remove any that are below low_threshold of the article
    topics_above_threshold = [(topic, percent) for topic, percent in top_three_topics if percent >= low_threshold]

    if not topics_above_threshold:
        # TODO: still pass back topic weights so that we can publish them to Cloudwatch
        logger.warning(f'No topics above weight threshold of {low_threshold}; not assigning tags.')
        return [{"name": config.no_topic_label, "score": 0.99}]

    # Cumulative sum of topic percentages
    topic_cumsum: np.ndarray = np.cumsum([percent for _, percent in topics_above_threshold], axis=0)

    # If they all add up to less than high_threshold, use all, else just include ones that reach the high_threshold
    if topic_cumsum[-1] <= high_threshold:
        topics_to_assign: List[Dict[str, np.float32]] = topics_above_threshold
    else:
        # Get index of when the cumsum exceeds high_threshold
        index = np.argmax(topic_cumsum > high_threshold)

        # Take final topics
        topics_to_assign: List[Dict[str, np.float32]] = topics_above_threshold[:index+1]

    # Apply text topic labels
    assigned_topic_labels = [
        {
            'name': topic_label,
            'score': round(percent, 6)  # Score as float to 6 d.p. for JSON serialisation.
        } for topic_label, percent in topics_to_assign
    ]

    return assigned_topic_labels


def apply_labels_to_vector(topic_vector: List[Tuple[int, float]], topic_labels: Dict[str, str]):
    """Takes topic vector and topic labels and returns the topic vector with
    index labels replaced with text labels.

    Args:
        topic_vector: list of topic index and score.
        topic_labels: Dictionary mapping topic index to topic textual label.

    Returns:
        topic vector with index labels replaced with text labels.
    """
    try:
        return [(topic_labels[str(topic_num)], score) for topic_num, score in topic_vector]
    except KeyError as e:
        raise ValueError(
            f'Topic label does not exist, check topic_labels.json is correct!  \n{e} '
            )


def group_topic_scores(labelled_topic_vector: Dict[str, float]):
    """Takes a topic vector and combines scores for labels that are the same.

    Args:
        labelled_topic_vector: of the form
         [('Arts/Culture', 0.14), ('Scotland', 0.227), ('Arts/Culture', 0.16), ...]

    Returns:
        Topic vector with aggregated scores e.g.
         [('Arts/Culture', 0.30), ('Scotland', 0.227), ...]
    """
    aggregated_scores = defaultdict(float)

    for label, percent in labelled_topic_vector:
        if label != 'REMOVE':
            aggregated_scores[label] += percent

    labels_with_grouped_scores = list(aggregated_scores.items())

    # Check there are no remaining duplicates
    labels = [t[0] for t in labels_with_grouped_scores]
    if len(labels) != len(set(labels)):
        raise ValueError("Still multiple labels in the grouped list.")

    return labels_with_grouped_scores


def assign_topic_labels(doc: str):
    """Takes a article, gets the topic vector for it and assigns labels.

    Args:
        doc: raw article text (headline, summary and body text combined, with no HTML).

    Returns:
        List of topic labels for an article (between 1 and 3 labels), including the 'Other articles' topic
        if no topics assigned by the model are over the low threshold.
    """
    logger.debug(f'Got document: {doc}')
    preprocessed_doc: List[str] = preprocess_document(doc)
    logger.debug(f'Preprocessed document: {preprocessed_doc}')

    logger.debug('Calculating topic vector from preprocessed document...')
    topic_vector: List[Tuple[int, float]] = get_topic_vector(preprocessed_doc)

    # load in the topic num to label mapping
    with open(os.path.join(config.local_model_path, 'topic_labels.json')) as labels_file:
        topic_labels = json.load(labels_file)

    try:
        # Replace index topic numbers with text labels
        labelled_topic_vector = apply_labels_to_vector(topic_vector, topic_labels)

        # Aggregate scores for topic groups
        grouped_topic_labels = group_topic_scores(labelled_topic_vector)
    except ValueError:
        raise

    logger.debug('Assigning topic labels from vector...')
    assigned_topic_labels = topic_labels_from_vector(grouped_topic_labels)

    return assigned_topic_labels
