FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY invest/ ./invest/
COPY Endpoints/ ./Endpoints/
COPY lambda_function.py .
COPY run.py .

CMD ["lambda_function.handler"]
