from src.toll_booth import credible


class TestTask:
    def test_task(self, mock_sqs_event, mock_context):
        results = credible.task(mock_sqs_event, mock_context)
        print(results)
