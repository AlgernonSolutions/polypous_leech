import pytest

import deploy_new_layer_version


@pytest.mark.upload
class TestUpload:
    def test_upload_zip(self):
        deploy_new_layer_version.run()


