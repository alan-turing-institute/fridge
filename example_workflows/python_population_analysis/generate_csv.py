#!/usr/bin/env python3
from csv import DictWriter

from faker import Faker

Faker.seed(36903)
fake = Faker(["en_GB", "fr_FR", "de_DE"])

population = [fake.profile() for _ in range(5000)]

field_names = population[0].keys()
with open("./population.csv", "w", newline="") as csvfile:
    writer = DictWriter(csvfile, field_names)

    writer.writeheader()
    for profile in population:
        writer.writerow(profile)
