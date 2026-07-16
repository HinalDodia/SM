FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY insert.py .
COPY options_service.py .
COPY stock_list.csv .

CMD ["insert.lambda_handler"]