from algernon.aws.gql import GqlConnection
from toll_booth.obj.data_objects.graph_objects import PotentialVertex


class GraphClient:
    def __init__(self, api_endpoint: str):
        self._api_endpoint = api_endpoint
        self._connection = GqlConnection(api_endpoint)

    def _send_command(self, command, variables):
        return self._connection.query(command, variables)

    def add_vertex(self, potential_vertex: PotentialVertex):
        pass
