from app import DiscoveryResult

def test_discovery_interface():
    result = DiscoveryResult(
        query="Mobile Money",
        provider="Safaricom",
        sources=[]
    )

    assert result.query == "Mobile Money"

