"""Mongo QCDB Database object and helpers
"""

import numpy as np
import itertools as it
import math
import json
import copy
import pandas as pd

from . import molecule
from . import statistics
from . import visualization
from . import mongo_helper
from . import constants
from . import fields
from . import client


def _nCr(n, r):
    """
    Compute the binomial coefficient n! / (k! * (n-k)!)
    """
    return math.factorial(n) / math.factorial(r) / math.factorial(n - r)


class Database(object):
    """
    This is a Mongo QCDB database class.
    """

    def __init__(self, name, socket=None, db_type="rxn"):

        # Client and mongod objects
        self.client = None
        self.mongod = None

        # Blank data object
        self.data = {}
        self.data["reactions"] = []
        self.data["name"] = name
        self.data["provenence"] = {}
        self.data["db_type"] = db_type

        # Index and internal data
        self.df = pd.DataFrame()
        self.rxn_index = pd.DataFrame()

        if socket is not None:

            if isinstance(socket, client.Client):
                self.client = socket
                self.mongod = socket.get_MongoSocket()

            elif isinstance(socket, mongo_helper.MongoSocket):
                self.mongod = socket

            else:
                print(dir(socket))
                raise TypeError("Database: client argument of unrecognized type '%s'" % type(socket))

            tmp_data = self.mongod.get_database(name)
            if tmp_data is None:
                print("Warning! Name '%s' not found, creating blank database." % name)
            else:
                self.data = tmp_data

            self.df = pd.DataFrame(index=self.get_index())

            # Unroll the index
            tmp_index = []
            for rxn in self.data["reactions"]:
                name = rxn["name"]
                for stoich_name in list(rxn["stoichiometry"]):
                    for mol_hash, coef in rxn["stoichiometry"][stoich_name].items():
                        tmp_index.append([name, stoich_name, mol_hash, coef])

            self.rxn_index = pd.DataFrame(
                tmp_index, columns=["name", "stoichiometry", "molecule_hash", "coefficient"])



        # If we making a new database we may need new hashes and json objects
        self._new_molecule_jsons = {}

        # What queried data do we have?
        self._queries = {}

    # Getters
    def __getitem__(self, args):
        return self.df[args]

    def refresh(self):
        """
        Reruns the entire query history to rebuild the current database from saved pages.
        """

        for k, q in self._queries.items():
            self.query(q[0], **q[1])
        return True

    def query(self,
              keys,
              stoich="default",
              prefix="",
              postfix="",
              reaction_results=False,
              scale="kcal"):
        """
        Queries the local MongoSocket data for the requested keys and stoichiometry.

        Parameters
        ----------
        keys : str, list
            A list of model chemistry to query.


        Returns
        -------
        success : bool
            Returns True if the requested query was successful or not.

        Notes
        -----


        Examples
        --------

        """

        if not reaction_results and (self.mongod is None):
            raise AttributeError("DataBase: MongoSocket was not set.")

        # Keys should be iterable
        if isinstance(keys, str):
            keys = [keys]

        # Save query to be repeated by refresh
        query_packet = [
            keys, {
                "stoich": stoich,
                "prefix": prefix,
                "postfix": postfix,
                "reaction_results": reaction_results,
                "scale": scale
            }
        ]
        query_packet_hash = fields.get_hash(query_packet, None)
        if query_packet_hash not in self._queries:
            self._queries[query_packet_hash] = query_packet

        # If reaction results
        if reaction_results:

            tmp_idx = pd.DataFrame(index=self.df.index, columns=keys)
            for rxn in self.data["reactions"]:
                for col in keys:
                    try:
                        tmp_idx.ix[rxn["name"], col] = rxn["reaction_results"][stoich][col]
                    except:
                        pass

            tmp_idx *= constants.get_scale(scale)
            self.df[tmp_idx.columns] = tmp_idx
            return True

        # if self.data["db_type"].lower() == "ie":
        #     _ie_helper(..)

        tmp_idx = self.rxn_index[self.rxn_index["stoichiometry"] == stoich].copy()
        tmp_idx = tmp_idx.reset_index(drop=True)

        # There could be duplicates so take the unique and save the map
        umols, uidx = np.unique(tmp_idx["molecule_hash"], return_index=True)

        # Evaluate the overall dataframe
        values = self.mongod.evaluate(umols, keys)
        values.columns = [prefix + x + postfix for x in values.columns]

        # Join on molecule hash
        tmp_idx = tmp_idx.join(values, on="molecule_hash")

        # Apply stoich values
        for col in values.columns:
            tmp_idx[col] *= tmp_idx["coefficient"]
        tmp_idx = tmp_idx.drop(['stoichiometry', 'molecule_hash', 'coefficient'], axis=1)

        tmp_idx = tmp_idx.groupby(["name"]).sum()

        # scale
        tmp_idx *= constants.get_scale(scale)

        # Apply to df
        self.df[tmp_idx.columns] = tmp_idx

        return True

    def compute(self, keys, stoich="default", options={}, program="psi4", other_fields={}):

        if self.client is None:
            raise AttributeError("DataBase: Compute: Client was not set.")

        # Keys should be iterable
        if isinstance(keys, str):
            keys = [keys]

        tmp_idx = self.rxn_index[self.rxn_index["stoichiometry"] == stoich].copy()
        tmp_idx = tmp_idx.reset_index(drop=True)

        # There could be duplicates so take the unique and save the map
        umols, uidx = np.unique(tmp_idx["molecule_hash"], return_index=True)
        values = self.mongod.evaluate(umols, keys)

        mask = pd.isnull(values)
        compute_list = []
        for idx, row in pd.isnull(values).iterrows():

            if idx in list(self._new_molecule_jsons):
                raise AttributeError("Database: Compute: Database (and new molecules) is not saved to the database.")

            for method in values.columns[row]:
                tmp = {}
                tmp["molecule_hash"] = idx
                tmp["modelchem"] = method
                for k, v in other_fields.items():
                    tmp[k] = v
                compute_list.append(tmp)


        submit_json = {}
        submit_json["multi_header"] = "QCDB_batch" # Verifies that I am submitting
        submit_json["options"] = options
        submit_json["tasks"] = compute_list
        submit_json["program"] = program

        ret = {}
        ret["submit"] = self.client.submit_task(submit_json)
        ret["nsubmit"] = len(compute_list)
        return ret

    def get_index(self):
        """
        Returns the current index of the database.
        """
        return [x["name"] for x in self.data["reactions"]]

    def get_rxn(self, name):
        """
        Returns the JSON object of a specific reaction.
        """

        found = []
        for num, x in enumerate(self.data["reactions"]):
            if x["name"] == name:
                found.append(num)

        if len(found) == 0:
            raise KeyError("Database:get_rxn: Reaction name '%s' not found." % name)

        if len(found) > 1:
            raise KeyError(
                "Database:get_rxn: Multiple reactions of name '%s' found. Database failure." % name)

        return self.data["reactions"][found[0]]

    # Setters
    def save(self, mongo_db=None, overwrite=False):
        if self.data["name"] == "":
            raise AttributeError("Database:save: Database must have a name!")

        if mongo_db is None:
            if self.mongod is None:
                raise AttributeError(
                    "Database:save: Database does not own a MongoDB instance and one was not passed in."
                )
            mongod = self.mongod
        else:
            mongod = mongo_db

        # Add the database
        mongod.add_database(self.data)

        # Loop over new molecules
        for k, v in self._new_molecule_jsons.items():
            mongod.add_molecule(v)

    # Statistical quantities
    def statistics(self, stype, value, bench="Benchmark"):
        return statistics.wrap_statistics(stype, self.df, value, bench)

    # Visualization
    def ternary(self, cvals=None):
        return visualization.Ternary2D(self.df, cvals=cvals)

    # Adders
    def parse_stoichiometry(self, stoichiometry):
        """
        Parses a stiochiometry list.

        Parameters
        ----------
        stoichiometry : list
            A list of tuples describing the stoichiometry.

        Returns
        -------
        stoich : list
            A list of formatted tuples describing the stoichiometry for use in a MongoDB.

        Notes
        -----
        This function attempts to convert the molecule into its correspond hash. The following will happen depending on the form of the Molecule.
            - Molecule hash - Used directly in the stoichiometry.
            - Molecule class - Hash is obtained and the molecule will be added to the databse upon saving.
            - Molecule string - Molecule will be converted to a Molecule class and the same process as the above will occur.


        Examples
        --------

        """

        ret = {}

        mol_hashes = []
        mol_values = []

        for line in stoichiometry:
            if len(line) != 2:
                raise KeyError(
                    "Database: Parse stoichiometry: passed in as a list must of key : value type")

            # Get the values
            try:
                mol_values.append(float(line[1]))
            except:
                raise TypeError(
                    "Database: Parse stoichiometry: second value must be convertable to a float.")

            # What kind of molecule is it?
            mol = line[0]

            # This is a molecule hash, should be in the database
            if isinstance(mol, str) and (len(mol) == 40):
                molecule_hash = mol

            elif isinstance(mol, str):
                qcdb_mol = molecule.Molecule(mol)

                molecule_hash = qcdb_mol.get_hash()

                if molecule_hash not in list(self._new_molecule_jsons):
                    self._new_molecule_jsons[molecule_hash] = qcdb_mol.to_json()

            elif isinstance(mol, molecule.Molecule):
                molecule_hash = mol.get_hash()

                if molecule_hash not in list(self._new_molecule_jsons):
                    self._new_molecule_jsons[molecule_hash] = mol.to_json()

            else:
                raise TypeError(
                    "Database: Parse stoichiometry: first value must either be a molecule hash, a molecule str, or a Molecule class."
                )

            mol_hashes.append(molecule_hash)

        # Sum together the coefficients of duplicates
        ret = {}
        for mol, coef in zip(mol_hashes, mol_values):
            if mol in list(ret):
                ret[mol] += coef
            else:
                ret[mol] = coef

        return ret

    def add_rxn(self, name, stoichiometry, return_values={}, attributes={}, other_fields={}):
        """
        Adds a reaction to a database object.

        Parameters
        ----------
        name : str
            Name of the reaction.
        stoichiometry : list or dict
            Either a list or dictionary of lists

        Notes
        -----

        Examples
        --------

        """
        rxn = {}

        # Set name
        rxn["name"] = name
        if name in self.get_index():
            raise KeyError(
                "Database: Name '%s' already exists. Please either delete this entry or call the update function."
                % name)

        # Set stoich
        if isinstance(stoichiometry, dict):
            rxn["stoichiometry"] = {}

            if "default" not in list(stoichiometry):
                raise KeyError("Database:add_rxn: Stoichiometry dict must have a 'default' key.")

            for k, v in stoichiometry.items():
                rxn["stoichiometry"][k] = self.parse_stoichiometry(v)

        elif isinstance(stoichiometry, (tuple, list)):
            rxn["stoichiometry"] = {}
            rxn["stoichiometry"]["default"] = self.parse_stoichiometry(stoichiometry)
        else:
            raise TypeError("Database:add_rxn: Type of stoichiometry input was not recognized '%s'",
                            type(stoichiometry))

        # Set attributes
        if not isinstance(attributes, dict):
            raise TypeError("Database:add_rxn: attributes must be a dictionary, not '%s'",
                            type(attributes))

        rxn["attributes"] = attributes

        if not isinstance(other_fields, dict):
            raise TypeError("Database:add_rxn: other_fields must be a dictionary, not '%s'",
                            type(attributes))

        for k, v in other_fields.items():
            rxn[k] = v


        if "default" in list(return_values):
            rxn["reaction_results"] = return_values
        else:
            # if isinstance(return_values, (dict)):
            #     raise TypeError("Passed in return values must have a 'default' field.")

            rxn["reaction_results"] = {}
            rxn["reaction_results"]["default"] = return_values


        self.data["reactions"].append(rxn)


        return rxn

    def add_ie_rxn(self, name, mol, **kwargs):

        return_values = kwargs.pop("return_values", {})
        attributes = kwargs.pop("attributes", {})
        other_fields = kwargs.pop("other_fields", {})

        stoichiometry = self.build_ie_fragments(mol, **kwargs)
        return self.add_rxn(
            name,
            stoichiometry,
            return_values=return_values,
            attributes=attributes,
            other_fields=other_fields)

    def to_json(self, filename=None):
        """
        If a filename is provided, dumps the file to disk. Otherwise returns a copy of the current data.
        """
        if filename:
            json.dumps(filename, self.data)

        else:
            return copy.deepcopy(self.data)

    def build_ie_fragments(self, mol, **kwargs):
        """
        Build the stoichiometry for an Interaction Energy.

        Parameters
        ----------
        mol : Molecule class or str
            Molecule to fragment.
        do_default : bool
            Create the default (noCP) stoichiometry.
        do_cp : bool
            Create the counterpoise (CP) corrected stoichiometry.
        do_vmfc : bool
            Create the Valiron-Mayer Function Counterpoise (VMFC) corrected stoichiometry.
        max_nbody : int
            What is the maximum fragment level built, if zero defaults to the maximum number of fragments.

        Notes
        -----

        Examples
        --------

        """

        do_default = kwargs.pop("do_default", True)
        do_cp = kwargs.pop("do_cp", True)
        do_vmfc = kwargs.pop("do_vmfc", True)
        max_nbody = kwargs.pop("max_nbody", 0)

        if not isinstance(mol, molecule.Molecule):

            mol = molecule.Molecule(mol, **kwargs)

        ret = {}

        max_frag = len(mol.fragments)
        if max_nbody == 0:
            max_nbody = max_frag

        if max_nbody < 2:
            raise AttributeError(
                "Database:build_ie_fragments: Molecule must have at least two fragments.")

        # Build some info
        fragment_range = list(range(max_frag))

        nocp_dict = {}
        cp_dict = {}

        # Loop over the bodis
        for nbody in range(1, max_nbody):
            nocp_tmp = []
            cp_tmp = []
            vmfc_tmp = []
            for k in range(1, nbody + 1):
                take_nk = _nCr(max_frag - k - 1, nbody - k)
                sign = ((-1)**(nbody - k))
                coef = take_nk * sign
                for frag in it.combinations(fragment_range, k):
                    if do_default:
                        nocp_tmp.append((mol.get_fragment(frag), coef))
                    if do_cp:
                        ghost = list(set(fragment_range) - set(frag))
                        cp_tmp.append((mol.get_fragment(frag, ghost), coef))

            if do_default:
                ret["default" + str(nbody)] = nocp_tmp

            if do_cp:
                ret["cp" + str(nbody)] = cp_tmp

        # Add in the maximal position
        if do_default:
            ret["default"] = [(mol, 1.0)]

        if do_cp:
            ret["cp"] = [(mol, 1.0)]

        return ret
