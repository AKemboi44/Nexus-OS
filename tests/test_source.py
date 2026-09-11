from models.source import Source

# Check if Nexus OS can create a source? PASS means Yes, Fail means no.
def test_source_creation ():
    source = Source(
        id = "1",
        title = "Test paper",
        authors= ["Abraham"],
        year = 2025,
        abstract = " Test Abstract",
        url= "https: // www.google.com",
        source_type="academic"
    )

    assert source.id == "1"
    assert source.title == "Test paper"