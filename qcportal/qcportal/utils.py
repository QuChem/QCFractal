from __future__ import annotations

import json
from hashlib import sha256
from typing import Optional, Union, Sequence, List, TypeVar, Any, Dict, Tuple, Iterable, Generator

import numpy as np

from qcportal.serialization import _JSONEncoder

_T = TypeVar("_T")


def make_list(obj: Optional[Union[_T, Sequence[_T]]]) -> Optional[List[_T]]:
    """
    Returns a list containing obj if obj is not a list or sequence type object
    """

    if obj is None:
        return None
    # Be careful. strings are sequences
    if isinstance(obj, str):
        return [obj]
    if not isinstance(obj, Sequence):
        return [obj]
    return list(obj)


def make_str(obj: Optional[Union[_T, Sequence[_T]]]) -> Optional[List[_T]]:
    """
    Returns a list containing obj if obj is not a list or sequence type object
    """

    if obj is None:
        return None
    # Be careful. strings are sequences
    if isinstance(obj, str):
        return obj
    if not isinstance(obj, Sequence):
        return str(obj)
    if isinstance(obj, list):
        return [str(i) for i in obj]
    if isinstance(obj, tuple):
        return tuple(str(i) for i in obj)
    else:
        raise ValueError("`obj` must be `None`, a str, list, tuple, or non-sequence")


def chunk_list(lst: List[_T], batch_size: int) -> Generator[_T, None, None]:
    """
    Split a list into batches
    """

    for idx in range(0, len(lst), batch_size):
        yield lst[idx : idx + batch_size]


def recursive_normalizer(value: Any, digits: int = 10, lowercase: bool = True) -> Any:
    """
    Prepare a structure for hashing by lowercasing all values and round all floats
    """

    if isinstance(value, (int, type(None))):
        pass

    elif isinstance(value, str):
        if lowercase:
            value = value.lower()

    elif isinstance(value, list):
        value = [recursive_normalizer(x, digits, lowercase) for x in value]

    elif isinstance(value, tuple):
        value = tuple(recursive_normalizer(x, digits, lowercase) for x in value)

    elif isinstance(value, dict):
        ret = {}
        for k, v in value.items():
            if lowercase:
                k = k.lower()
            ret[k] = recursive_normalizer(v, digits, lowercase)
        value = ret

    elif isinstance(value, np.ndarray):
        if digits:
            # Round array
            value = np.around(value, digits)
            # Flip zeros
            value[np.abs(value) < 5 ** (-(digits + 1))] = 0

    elif isinstance(value, float):
        if digits:
            value = round(value, digits)
            if value == -0.0:
                value = 0
            if value == 0.0:
                value = 0

    else:
        raise TypeError("Invalid type in recursive normalizer ({type(value)}), only simple Python types are allowed.")

    return value


def prefix_projection(
    includes: Optional[Iterable[str]], excludes: Optional[Iterable[str]], prefix: str
) -> Tuple[Optional[List[str]], Optional[List[str]]]:
    """
    Prefixes includes and excludes with a string

    This is used for mapping a set of includes/excludes to a relationship of an ORM. For example,
    you may have an endpoint for molecules of a computation (/record/1/molecule) which contains
    include/exclude in its url parameters. This function is used to map those includes/excludes to
    the "molecule" relationship of the record.
    """

    ch_includes = list(includes) if includes is not None else None
    ch_excludes = list(excludes) if excludes is not None else None

    base = prefix.strip(".")
    p = base + "."

    if ch_includes is None:
        # If nothing is specified, include the defaults of the child
        ch_includes = [base]
    else:
        # Otherwise, prefix all entries with whatever was specified
        ch_includes = [p + x for x in ch_includes]

    if ch_excludes:
        ch_excludes = [p + x for x in ch_excludes]

    return ch_includes, ch_excludes


def calculate_limit(max_limit: int, given_limit: Optional[int]) -> int:
    """Get the allowed limit on results to return for a particular or type of object

    If 'given_limit' is given (ie, by the user), this will return min(limit, max_limit)
    where max_limit is the set value for the table/type of object
    """

    if given_limit is None:
        return max_limit

    return min(given_limit, max_limit)


def hash_dict(d: Dict[str, Any]) -> str:
    j = json.dumps(d, ensure_ascii=True, sort_keys=True, cls=_JSONEncoder).encode("utf-8")
    return sha256(j).hexdigest()