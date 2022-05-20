from typing import Dict, Any, Union, Optional, List, Iterable, Tuple

from pydantic import BaseModel
from typing_extensions import Literal

from qcportal.base_models import RestModelBase
from qcportal.molecules import Molecule
from qcportal.records.reaction import ReactionRecord, ReactionSpecification
from qcportal.utils import make_list
from .. import BaseDataset
from ...records import PriorityEnum


class ReactionDatasetNewEntry(BaseModel):
    name: str
    comment: Optional[str] = None
    stoichiometry: List[Tuple[float, Union[int, Molecule]]]
    additional_keywords: Dict[str, Any] = {}
    attributes: Dict[str, Any] = {}


class ReactionDatasetEntryStoichiometry(BaseModel):
    molecule_id: int
    coefficient: float

    molecule: Optional[Molecule] = None


class ReactionDatasetEntry(BaseModel):
    name: str
    comment: Optional[str] = None
    stoichiometry: List[ReactionDatasetEntryStoichiometry]
    additional_keywords: Optional[Dict[str, Any]] = {}
    attributes: Optional[Dict[str, Any]] = {}


class ReactionDatasetSpecification(BaseModel):
    name: str
    specification: ReactionSpecification
    description: Optional[str] = None


class ReactionDatasetRecordItem(BaseModel):
    entry_name: str
    specification_name: str
    record_id: int
    record: Optional[ReactionRecord._DataModel]


class ReactionDataset(BaseDataset):
    class _DataModel(BaseDataset._DataModel):
        dataset_type: Literal["reaction"]

        specifications: Optional[Dict[str, ReactionDatasetSpecification]] = None
        entries: Optional[Dict[str, ReactionDatasetEntry]] = None
        record_items: Optional[List[ReactionDatasetRecordItem]] = None

        contributed_values: Any

    # This is needed for disambiguation by pydantic
    dataset_type: Literal["reaction"]
    raw_data: _DataModel

    # Needed by the base class
    _entry_type = ReactionDatasetEntry
    _specification_type = ReactionDatasetSpecification
    _record_item_type = ReactionDatasetRecordItem
    _record_type = ReactionRecord

    def add_specification(self, name: str, specification: ReactionSpecification, description: Optional[str] = None):

        payload = ReactionDatasetSpecification(name=name, specification=specification, description=description)

        self.client._auto_request(
            "post",
            f"v1/datasets/reaction/{self.id}/specifications",
            List[ReactionDatasetSpecification],
            None,
            None,
            [payload],
            None,
        )

        self._post_add_specification(name)

    def add_entries(self, entries: Union[ReactionDatasetEntry, Iterable[ReactionDatasetNewEntry]]):

        entries = make_list(entries)
        self.client._auto_request(
            "post",
            f"v1/datasets/reaction/{self.id}/entries/bulkCreate",
            List[ReactionDatasetNewEntry],
            None,
            None,
            make_list(entries),
            None,
        )

        new_names = [x.name for x in entries]
        self._post_add_entries(new_names)


#######################
# Web API models
#######################


class ReactionDatasetAddBody(RestModelBase):
    name: str
    description: Optional[str] = None
    tagline: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None
    group: Optional[str] = None
    provenance: Optional[Dict[str, Any]]
    visibility: bool = True
    default_tag: Optional[str] = None
    default_priority: PriorityEnum = PriorityEnum.normal