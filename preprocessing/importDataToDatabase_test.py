"""
Unit test
"""
import zipfile
import io
from contextlib import contextmanager
import logging

import pytest
import sqlalchemy

from shared_proxy import database

from importDataToDatabase import (
  default_field_mapping_by_table_name,
  convert_zip_file
)

VERSION_ID1 = '00001-1'

def setup_module():
  logging.basicConfig(level=logging.DEBUG)

@pytest.fixture(name='logger')
def get_logger():
  return logging.getLogger('test')

@contextmanager
def convert_files(filenames):
  logger = get_logger()
  engine = sqlalchemy.create_engine('sqlite://', echo=False)
  logger.debug("engine driver: %s", engine.driver)
  db = database.Database(engine)
  db.update_schema()

  zip_filename = 'dummy.zip'
  zip_stream = io.BytesIO()

  with zipfile.ZipFile(zip_stream, 'w') as zf:
    for filename in filenames:
      zf.write("test_data/" + filename)

  zip_stream.seek(0)

  field_mapping_by_table_name = default_field_mapping_by_table_name
  early_career_researcher_person_ids = set()

  convert_zip_file(
    zip_filename, zip_stream, db, field_mapping_by_table_name,
    early_career_researcher_person_ids
  )
  yield db
  db.close()

def test_regular(logger):
  with convert_files(['regular-00001.xml']) as db:
    df = db.manuscript_version.read_frame().reset_index()
    logger.debug('df:\n%s', df)
    assert (
      set(df['version_id']) ==
      set([VERSION_ID1])
    )

def test_minimal(logger):
  with convert_files(['minimal-00001.xml']) as db:
    df = db.manuscript_version.read_frame().reset_index()
    logger.debug('df:\n%s', df)
    assert (
      set(df['version_id']) ==
      set([VERSION_ID1])
    )

def test_with_duplicate_author():
  with convert_files(['with-duplicate-author-00001.xml']) as db:
    assert (
      set(db.manuscript_author.read_frame()['person_id']) ==
      set(['author1'])
    )

def test_with_duplicate_stage():
  with convert_files(['with-duplicate-stage-00001.xml']) as db:
    assert (
      set(db.manuscript_stage.read_frame()['triggered_by_person_id']) ==
      set(['reviewer1'])
    )

def test_with_duplicate_stage_and_no_triggered_by_person_id():
  with convert_files(['with-duplicate-stage-and-no-triggered-by-person-id-00001.xml']) as db:
    # ensure we are inserting a record with None (not a blank string)
    assert (
      set(db.manuscript_stage.read_frame()['triggered_by_person_id']) ==
      set([None])
    )

def test_with_empty_funder_name_ref():
  with convert_files(['with-empty-funder-name-00001.xml']) as db:
    assert (
      db.manuscript_funding.read_frame().to_dict(orient='records') ==
      [{
        'version_id': VERSION_ID1,
        'funder_name': '',
        'grant_reference_number': 'Funding Reference 1'
      }]
    )
    assert (
      db.manuscript_author_funding.read_frame().to_dict(orient='records') ==
      [{
        'version_id': VERSION_ID1,
        'person_id': 'author1',
        'funder_name': '',
        'grant_reference_number': 'Funding Reference 1'
      }]
    )

def test_with_empty_grant_ref():
  with convert_files(['with-empty-grant-ref-00001.xml']) as db:
    assert (
      db.manuscript_funding.read_frame().to_dict(orient='records') ==
      [{
        'version_id': VERSION_ID1,
        'funder_name': 'Funder Name 1',
        'grant_reference_number': ''
      }]
    )
    assert (
      db.manuscript_author_funding.read_frame().to_dict(orient='records') ==
      [{
        'version_id': VERSION_ID1,
        'person_id': 'author1',
        'funder_name': 'Funder Name 1',
        'grant_reference_number': ''
      }]
    )

def test_with_unnormalised_subject_area():
  with convert_files(['with-unnormalised-subject-area-00001.xml']) as db:
    assert (
      set(db.manuscript_subject_area.read_frame()['subject_area']) ==
      set(['Subject Area and Test 1'])
    )

def test_with_missing_persons(logger):
  with convert_files(['with-missing-persons-00001.xml']) as db:
    df = db.manuscript_version.read_frame().reset_index()
    logger.debug('df:\n%s', df)
    assert (
      set(df['version_id']) ==
      set([VERSION_ID1])
    )

def test_with_manuscript_suffix(logger):
  with convert_files(['with-manuscript-suffix-00001-suffix.xml']) as db:
    df = db.manuscript_version.read_frame().reset_index()
    logger.debug('df:\n%s', df)
    assert (
      set(df['version_id']) ==
      set([VERSION_ID1])
    )

def test_with_invalid_manuscript_ref(logger):
  with convert_files(['with-invalid-manuscript-ref.xml']) as db:
    df = db.manuscript_version.read_frame().reset_index()
    logger.debug('df:\n%s', df)
    assert (
      set(df['version_id']) ==
      set(['with-invalid-manuscript-ref-1'])
    )

def test_with_empty_oricid_id(logger):
  with convert_files(['with-empty-orcid-id.xml']) as db:
    df = db.person.read_frame().reset_index()
    logger.debug('df:\n%s', df)
    assert (
      set(df['person_id']) ==
      set(['author1'])
    )
    df = db.person_membership.read_frame().reset_index()
    logger.debug('df:\n%s', df)
    assert len(df) == 0

def test_with_corresponding_author(logger):
  with convert_files(['with-corresponding-author.xml']) as db:
    df = db.manuscript_author.read_frame().reset_index().sort_values('seq')
    logger.debug('df:\n%s', df)
    assert (
      [tuple(x) for x in df[['person_id', 'is_corresponding_author']].values] ==
      [('author1', False), ('author2', True)]
    )
