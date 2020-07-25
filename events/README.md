# Example events

## tl:dr
- In `lambda_function.py` you can specify the event being passed to the function when running locally, the line looks like:
`event_path = os.path.join(base_dirname, 'events/event_schedule.json')`
- If testing scheduled trigger use `event_schedule.json`
- If testing slack trigger use `event_slack_body.json`
- If using the slack event make sure the dates in the event are valid i.e in the future.

## What events are there

If triggered from slack or by a cloudwatch event (on a schedule), the lambda_handler function takes a different `event` variable in. To run locally we need to give the same format of an example event to ensure the lambda it will work when deployed.

- `event_schedule` - this is an example of the json passed to the event argument when the lambda is triggered on schedule
- When triggered by slack the request from slack passes through API gateway there are two files that represent what happens to this event:
    - If API gateway is set to lambda proxy integration, the full event data is passed through (or proxyed) to the function, this is seen in `event_slack_full.json`.
    - However in order to have async invocations we can't use lambda proxy. We instead have a 'mapping template' that passes through a specific part of the data. In this case all the useful slack information (channel, username, token) is stored in the `body` field of `event_slack.json`. We therefore just pass that to the function in a `slack-body` field. An example of this is `event_slack_body.json`. 