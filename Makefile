# The name attached to each aws resource
PROJECT_NAME = vjdata-stats-releases

# cron schedule for lambda
SCHEDULE = "cron(0 9 ? * FRI *)"
PYTHON_VERSION = 3.7

ACCOUNT_ID = 301790081969
AWS_PROFILE = wormhole

# Config built from above values
VENV_NAME = venv# python virtual environment to hold dependencies for local development
FUNCTION_NAME = lambda_function# name of .py file with lambda_handler inside
LAMBDA_NAME = ${PROJECT_NAME}-lambda-function
S3_BUCKET = ${PROJECT_NAME}-lambda-code-bucket# name of s3 bucket to hold deployed code
DEPLOY_ZIP = ${PROJECT_NAME}_deployment_bundle.zip# name of the zip file to upload to s3
LAMBDA_STACK_NAME = ${PROJECT_NAME}-lambda-stack# name of the stack that holds the lambda and execution role
S3_STACK_NAME = ${PROJECT_NAME}-s3-stack
LAMBDA_ROLE_NAME = ${PROJECT_NAME}-lambda-role
API_NAME = ${PROJECT_NAME}-lambda-api
SCHEDULE_NAME = ${PROJECT_NAME}-lambda-schedule

##################### Assumes a certificate.pem file in ~/
wormhole:
	python3 scripts/wormhole.py -a ${ACCOUNT_ID} -p ${AWS_PROFILE}


################# Setup - create venv and install requirements.txt ###########################
clean_setup: 
	rm -rf ${VENV_NAME} dist ${DEPLOY_ZIP}
	python3 -m venv ${VENV_NAME}
	( \
       source ${VENV_NAME}/bin/activate; \
       pip install -r requirements.txt; \
    )

########## Run function locally
local_invoke:
	venv/bin/python src/lambda_function.py;


################ Package and deploy ##################
package_deploy: package deploy

# Install dependencies in lambda container and zip up all code
package:
	docker run --rm -v $(shell pwd):/app lambci/lambda:build-python${PYTHON_VERSION} \
		bash /app/scripts/package.sh ${DEPLOY_ZIP}

deploy: wormhole
	aws s3 cp ${DEPLOY_ZIP} s3://${S3_BUCKET} --profile ${AWS_PROFILE}
	aws lambda update-function-code \
		--function-name ${LAMBDA_NAME} \
		--s3-bucket ${S3_BUCKET} \
		--s3-key ${DEPLOY_ZIP} \
		--publish \
		--profile ${AWS_PROFILE}

# update the cron schedule with the SCHEDULE specified at the top of the file
update_schedule: wormhole
	echo ${SCHEDULE_NAME}
	aws events put-rule \
		--name ${SCHEDULE_NAME} \
		--schedule-expression ${SCHEDULE} \
		--profile ${AWS_PROFILE}


################ Provision lambda - intial setup  #################################
 
# You will need extra permissions namely cloudformation access to 
# delete or create the stacks

create_stacks: create_s3 create_lambda
clean_stacks: delete_s3 delete_lambda

# creates bucket and adds a dummy deploy zip fot lambda to look for
create_s3: wormhole
	aws cloudformation create-stack \
		--stack-name ${S3_STACK_NAME} \
		--template-body file://cloud-formation/code-bucket.yaml \
		--capabilities CAPABILITY_NAMED_IAM \
		--profile ${AWS_PROFILE} \
		--parameters \
			ParameterKey=LambdaCodeBucketName,ParameterValue=${S3_BUCKET}; \
	sleep 10; \
	zip -rq ${DEPLOY_ZIP} .gitignore; \
	aws s3 cp ${DEPLOY_ZIP} s3://${S3_BUCKET} --profile ${AWS_PROFILE};\
	rm ${DEPLOY_ZIP}; \

delete_s3: wormhole
	aws s3 rb s3://${S3_BUCKET} --force --profile ${AWS_PROFILE}
	aws cloudformation delete-stack --stack-name ${S3_STACK_NAME} --profile ${AWS_PROFILE}

create_lambda: wormhole delete_lambda
	sleep 5
	aws cloudformation create-stack \
		--stack-name ${LAMBDA_STACK_NAME} \
		--template-body file://cloud-formation/function.yaml \
		--capabilities CAPABILITY_NAMED_IAM \
		--profile ${AWS_PROFILE} \
		--parameters \
			ParameterKey=APIName,ParameterValue=${API_NAME} \
			ParameterKey=LambdaZipPackageName,ParameterValue=${DEPLOY_ZIP} \
			ParameterKey=Lambdahandler,ParameterValue=${FUNCTION_NAME} \
			ParameterKey=Schedule,ParameterValue=${SCHEDULE} \
			ParameterKey=LambdaScheduleName,ParameterValue=${SCHEDULE_NAME} \
			ParameterKey=LambdaResourceName,ParameterValue=${LAMBDA_NAME} \
			ParameterKey=LambdaCodeBucketName,ParameterValue=${S3_BUCKET} \
			ParameterKey=LambdaRoleName,ParameterValue=${LAMBDA_ROLE_NAME} \
			ParameterKey=PythonVersion,ParameterValue=${PYTHON_VERSION} \
			ParameterKey=SlackAuthToken,ParameterValue=${STATS_RELEASES_SLACK_AUTH_TOKEN} \
			ParameterKey=SlackVerToken,ParameterValue=${STATS_RELEASES_SLACK_VER_TOKEN} \
			ParameterKey=DropboxToken,ParameterValue=${STATS_RELEASES_DROPBOX_TOKEN} \
			ParameterKey=DropboxPaperFolderIDSchedule,ParameterValue=${STATS_RELEASES_DROPBOX_PAPER_FOLDER_ID_SCHEDULE} \
			ParameterKey=DropboxPaperFolderIDSlack,ParameterValue=${STATS_RELEASES_DROPBOX_PAPER_FOLDER_ID_SLACK} \


delete_lambda: wormhole
	aws cloudformation delete-stack --stack-name ${LAMBDA_STACK_NAME} --profile ${AWS_PROFILE}
	
### Handy commands

# This returns the api endpoint to paste into your slack app slach command
get_api_endpoint: wormhole
	aws cloudformation describe-stacks --stack-name ${LAMBDA_STACK_NAME} \
		--query "Stacks[0].Outputs[0].OutputValue" \
		--output text \
		--profile ${AWS_PROFILE}

list_live_stacks: wormhole
	aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE  --profile ${AWS_PROFILE}