#!/usr/bin/env python3
import re
from decimal import Decimal
from enum import Enum, unique

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


@unique
class BloodGroup(Enum):
    a_negative = "A-"
    a_positive = "A+"
    ab_negative = "AB-"
    ab_positive = "AB+"
    b_negative = "B-"
    b_positive = "B+"
    o_negative = "O-"
    o_positive = "O+"


re_location = re.compile(r"\(Decimal\('(.*)'\), Decimal\('(.*)'\)\)")


def convert_location(location: str) -> tuple[Decimal, Decimal]:
    match = re_location.match(location)
    return (Decimal(match.group(1)), Decimal(match.group(2)))


df = pd.read_csv(
    "./population.csv",
    converters={
        "blood_group": BloodGroup,
        "current_location": convert_location,
        "website": eval,
    },
    dtype={
        "job": str,
        "company": str,
        "ssn": str,
        "residence": str,
        "username": str,
        "address": str,
        "mail": str,
    },
    parse_dates=["birthdate"],
    header=0,
)

ax = df["blood_group"].value_counts().plot.pie()
ax.get_figure().savefig("./blood_group.png")

plt.clf()

now = np.datetime64("now")
df["age"] = df["birthdate"].apply(lambda x: int((now - x).days / 365.25))
ax = df["age"].plot.hist()
ax.get_figure().savefig("./age.png")
