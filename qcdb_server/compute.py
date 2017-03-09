import uuid
import json
import subprocess as sp
import os
import time

# Make sure this looks like just a normal file
#runner.run_task.__module__ = "runner"

try:
    psi_location = os.environ["MONGO_PSI4"]
except:
    raise KeyError("Mongo Compute: MONGO_PSI4 psi variable was not set. Failing.")

psi_run = "python " + psi_location + " --json "


def psi_compute(json_data, **kwargs):

    filename = str(uuid.uuid4()) + ".json"

    with open(filename, "w") as outfile:
        json.dump(json_data, outfile)

    ncores = kwargs.pop("ncores", 1)
    run_script = psi_run + "-n" + str(ncores) + " " + filename
    sp.call(run_script, shell=True)

    with open(filename, "r") as outfile:
        ret = json.load(outfile)

    os.unlink(filename)

    return ret


def pass_compute(json_data, **kwargs):
    """
    This doesnt do anything with the json. Used for testing.
    """

    return json_data


computers = {"psi4": psi_compute, "pass": pass_compute}

if __name__ == "__main__":

    json_data = {}
    json_data["molecule"] = """He 0 0 0\n--\nHe 0 0 1"""
    json_data["driver"] = "energy"
    json_data["method"] = 'SCF'
    #json_data["kwargs"] = {"bsse_type": "cp"}
    json_data["options"] = {"BASIS": "STO-3G"}
    json_data["return_output"] = True

    print(psi_compute(json_data))
