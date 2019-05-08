class TestTasks:
    def test_generate_source_vertex(self, mock_generate_source_vertex_event, mock_context, mock_bullhorn_boto):
        from src.toll_booth import task
        results = task(mock_generate_source_vertex_event, mock_context)
        for result in results:
            from src.toll_booth import PotentialVertex
            assert isinstance(result, PotentialVertex)
            assert result.for_index
            assert result.for_stub_index
            assert result.identifier_stem
