"""Ezhuthu Tamil epigraphy ontology: OWL (ontology/ezhuthu.ttl), lookups and the lookup API.

Use :mod:`ezhuthu.ontology.lookup` at runtime::

    from ezhuthu.ontology.lookup import find_entities, valid_letters, formulas_for, entity, hints_for_gap
"""

from ezhuthu.ontology.lookup import entity, find_entities, formulas_for, hints_for_gap, valid_letters

__all__ = ["entity", "find_entities", "formulas_for", "hints_for_gap", "valid_letters"]
