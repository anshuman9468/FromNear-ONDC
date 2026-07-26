import json
from app.ondc.protocol.builders import IssueRequestBuilder

payload = IssueRequestBuilder.build(
    transaction_id="d737f7e6-7e05-4670-94a7-53b2e00c684e",
    message_id="406cd422-6ede-4ac7-a047-d4d0af47de23",
    bpp_id="workbench.ondc.tech",
    bpp_uri="https://workbench.ondc.tech/api-service/ONDC:RET10/1.2.0/seller",
    order_id="4712b03c-836a-47cd-9a1c-6482272ee5b8",
)

print(json.dumps(payload, indent=2))
