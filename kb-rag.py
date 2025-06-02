import boto3
from langchain_aws import ChatBedrock
from langchain_community.graphs import NeptuneGraph
from langchain.chains import NeptuneOpenCypherQAChain

bedrock_runtime = boto3.client(
    service_name="bedrock-runtime",
    region_name='us-east-1',
)

host = "db-neptune-1-instance-1.chccae2wwzh9.us-east-1.neptune.amazonaws.com"
port = 8182
use_https = True

graph = NeptuneGraph(host=host, port=port, use_https=use_https)

model_id = 'anthropic.claude-3-haiku-20240307-v1:0'
model_kwargs = {
    "max_tokens": 512,
    "temperature": 0,
    "top_k": 250,
    "top_p": 1,
    "stop_sequences": ["\n\nHuman:"]
}

llm = ChatBedrock(
    client=bedrock_runtime,
    model_id=model_id,
    model_kwargs=model_kwargs
)

chain = NeptuneOpenCypherQAChain.from_llm(llm=llm, graph=graph, verbose=True, allow_dangerous_requests=True)

print(chain.run("name the companies in the data"))
