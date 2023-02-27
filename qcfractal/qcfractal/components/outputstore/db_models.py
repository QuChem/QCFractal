from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, Integer, Enum, JSON, LargeBinary, ForeignKey, UniqueConstraint

from qcfractal.db_socket import BaseORM
from qcportal.compression import CompressionEnum
from qcportal.outputstore import OutputTypeEnum, OutputStore

if TYPE_CHECKING:
    from typing import Dict, Any, Optional, Iterable


class OutputStoreORM(BaseORM):
    """
    Table for storing raw computation outputs (text) and errors (json)
    """

    __tablename__ = "output_store"

    id = Column(Integer, primary_key=True)
    history_id = Column(Integer, ForeignKey("record_compute_history.id", ondelete="cascade"), nullable=False)

    output_type = Column(Enum(OutputTypeEnum), nullable=False)
    compression = Column(Enum(CompressionEnum), nullable=True)
    compression_level = Column(Integer, nullable=True)
    value = Column(JSON, nullable=True)
    data = Column(LargeBinary, nullable=True)

    __table_args__ = (UniqueConstraint("history_id", "output_type", name="ux_output_store_id_type"),)

    def model_dict(self, exclude: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        # Fields not in model
        exclude = self.append_exclude(exclude, "id", "history_id")

        d = BaseORM.model_dict(self, exclude)

        # Old way: store a plain string or dict in "value"
        # New way: store (possibly) compressed output in "data"
        val = d.pop("value", None)

        # If stored the old way, convert to the new way
        if d["data"] is None:
            # Set the data field to be the string or dictionary
            d["data"] = val

            # Remove these and let the model handle the defaults
            d.pop("compression")
            d.pop("compression_level")

        return d

    def append(self, to_append: str):
        """
        Appends text to output stored in this orm
        """

        out_obj = OutputStore(**self.model_dict())
        new_str = out_obj.as_string + to_append

        # Change compression to the default, if an older compression type
        new_obj = OutputStore.compress(self.output_type, new_str, CompressionEnum.zstd)

        self.value = None
        self.data = new_obj.data
        self.compression = new_obj.compression
        self.compression_level = new_obj.compression_level

    def as_string(self):
        """
        Returns the output as a string
        """

        return self.to_model(OutputStore).as_string