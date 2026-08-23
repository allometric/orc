"""orc — orchestrate the production, validation, and indexing of
allometric/models v4 YAML."""

__version__ = "0.1.0"

from orc.ingest import IngestError, IngestResult, IngestWarning, ingest
from orc.schema import ModelsFile, RegistryRecord
from orc.families import FamilyMeta, FamilySelect, ModelBlob, ModelFamily

__all__ = [
    "ModelsFile",
    "RegistryRecord",
    "FamilyMeta",
    "FamilySelect",
    "ModelBlob",
    "ModelFamily",
    "IngestError",
    "IngestResult",
    "IngestWarning",
    "ingest",
    "__version__",
]