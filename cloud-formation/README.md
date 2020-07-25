# Cloud formation 

This folder contains the two cloud templates for this app

- `code-bucket.yaml` - creates a single s3 bucket to hold the function code 
- `function.yaml` - creates lambda function and api gateway and necessary roles to allow api gateway to call the lambda
- `function-proxy.yaml` - intial template for api with lambda proxy integration. In the end needed to invoke async to avoid `operation_timeout` error in slack. Async invocation is currently not possible with proxy integration.
- `deploy_policy.json` - gives the required permissions to push code to the lambda and also update the cloudwatch schedule rule. This policy was created manually in the console and is called `deploy-vjdata-stats-releases-lambda`. It needs to be attached to any user that wants to update this lambda.


The templates [here](https://github.com/bbc/newsspec-24992-vj-autodeployer/tree/master/infrastructure/stacks) were used in part as a reference to create the cloud formation template for this project.