from itertools import groupby
import itertools
from collections import Counter
import ast
import logging

import pandas as pd

from peerscout.utils.collection import (
  invert_set_dict
)

from peerscout.utils.pandas import (
  groupby_agg_droplevel
)

from .utils import unescape_and_strip_tags, filter_by

from  peerscout.utils.collection import (
  iter_flatten,
  filter_none,
  deep_get,
  deep_get_list,
  groupby_to_dict,
  groupby_columns_to_dict,
  applymap_dict
)

from .manuscript_utils import (
  duplicate_manuscript_titles_as_alternatives
)

from .manuscript_keywords import ManuscriptKeywordService
from .manuscript_subject_areas import ManuscriptSubjectAreaService

from .manuscript_person_relationship_service import (
  ManuscriptPersonRelationshipService,
  RelationshipTypes
)

from .manuscript_person_stage_service import (
  ManuscriptPersonStageService,
  StageNames
)

from .person_keywords import (
  PersonKeywordService,
  get_person_ids_of_person_keywords_scores
)


from .person_roles import PersonRoleService


NAME = 'RecommendReviewers'

debugv_enabled = False

def set_debugv_enabled(enabled):
  global debugv_enabled
  debugv_enabled = enabled

def debugv(*args):
  if debugv_enabled:
    logging.getLogger(NAME).debug(*args)

to_int = lambda x, default_value=None: int(x) if x is not None else default_value

def get_first(l, default_value=None):
  return l[0] if l else default_value

def column_astype(df, col_name, col_type):
  df = df.copy()
  df[col_name] = df[col_name].astype(col_type)
  return df

def is_nat(x):
  return isinstance(x, type(pd.NaT))

def is_null(x):
  return not isinstance(x, list) and (pd.isnull(x) or is_nat(x))

def nat_to_none(x):
  return None if is_nat(x) else x

def null_to_none(x):
  return None if is_null(x) else x

def remove_none(d):
  return {k: v for k, v in d.items() if not is_null(v)}

def clean_result(result):
  if isinstance(result, dict):
    return remove_none(applymap_dict(result, nat_to_none))
  else:
    return [clean_result(x) for x in result]

def manuscript_number_to_no(x):
  return x.split('-')[-1]

def filter_dict_keys(d, f):
  return {k: v for k, v in d.items() if f(k)}

def groupby_column_to_dict(df, groupby_col, value_col=None, sort_by=None):
  if value_col is None:
    value_f = lambda item: filter_dict_keys(item, lambda col: col != groupby_col)
  elif callable(value_col):
    value_f = value_col
  else:
    value_f = lambda item: item[value_col]
  if sort_by is None:
    sort_by = groupby_col
  a = df.sort_values(sort_by).to_dict(orient='records')
  return {
    k: [value_f(item) for item in v]
    for k, v in groupby(a, lambda item: item[groupby_col])
  }

def groupby_index_to_dict(df):
  return groupby_column_to_dict(df, df.index.name)

def map_to_dict(keys, d, default_value=None):
  return [d.get(k, default_value) for k in keys]

MANUSCRIPT_ID = 'manuscript_id'
VERSION_ID = 'version_id'

RAW_MANUSCRIPT_ID_COLUMNS = []
TEMP_MANUSCRIPT_ID_COLUMNS = [VERSION_ID]
MANUSCRIPT_ID_COLUMNS = RAW_MANUSCRIPT_ID_COLUMNS + TEMP_MANUSCRIPT_ID_COLUMNS

SIMILARITY_COLUMN = 'similarity'

PERSON_ID = 'person_id'

PERSON_COLUMNS = [
  PERSON_ID,
  'title', 'first_name', 'middle_name', 'last_name', 'institution', 'status', 'email',
  'is_early_career_researcher'
]

def unescape_if_string(s):
  if isinstance(s, str):
    return unescape_and_strip_tags(s)
  return s

def stats_by_person_for_period(table):
  df = table.read_frame()
  debugv("person stats frame (%s):\n%s", table.table.__tablename__, df)
  if len(df) == 0:
    return {}

  def get_review_duration_details(v):
    if v['reviewed_count'] == 0:
      return
    return {
      'min': v['reviewed_duration_min'],
      'max': v['reviewed_duration_max'],
      'mean': v['reviewed_duration_avg'],
      'count': v['reviewed_count']
    }

  m = clean_result({
    k: {
      'review_duration': get_review_duration_details(v),
      'reviews_in_progress': v['awaiting_review_count'],
      'waiting_to_be_accepted': v['awaiting_accept_count'],
      'declined': v['declined_count']
    }
    for k, v in df.to_dict(orient='index').items()
  })
  debugv("person stats map:\n%s", m)
  return m

def select_dict_keys(d, keys):
  return {k: d[k] for k in keys}

def manuscript_id_fields(manuscript):
  return select_dict_keys(manuscript, MANUSCRIPT_ID_COLUMNS)

def sort_manuscripts_by_date(manuscripts):
  return sorted(manuscripts, key=lambda m: (
    m.get('published-date', None),
    m.get('title', ''),
    m.get(VERSION_ID, None)
  ), reverse=True)

HIDDEN_MANUSCRIPT_PROPS = set(['editors', 'reviewers'])

def is_visible_manuscript_prop(key):
  return key not in HIDDEN_MANUSCRIPT_PROPS

def clean_manuscript(m):
  return filter_dict_keys(m, is_visible_manuscript_prop)

def clean_manuscripts(manuscripts):
  return [clean_manuscript(m) for m in manuscripts]

def calculate_combined_score(keyword, similarity):
  return min(1.0, keyword + (similarity or 0) * 0.5)

def score_by_manuscript(manuscript, keyword, similarity):
  return {
    **manuscript_id_fields(manuscript),
    'keyword': keyword,
    'similarity': similarity,
    'combined': calculate_combined_score(keyword, similarity)
  }

def sorted_potential_reviewers(potential_reviewers):
  potential_reviewers = list(potential_reviewers)
  review_duration_mean_keys = ['person', 'stats', 'overall', 'review-duration', 'mean']
  available_potential_reviewer_mean_durations = filter_none(deep_get_list(
    potential_reviewers, review_duration_mean_keys
  ))
  potential_reviewer_mean_duration = (
    float(pd.np.mean(available_potential_reviewer_mean_durations))
    if len(available_potential_reviewer_mean_durations) > 0
    else None
  )

  potential_reviewers = sorted(
    potential_reviewers,
    key=lambda potential_reviewer: (
      -(potential_reviewer['scores'].get('combined') or 0),
      -(potential_reviewer['scores'].get('keyword') or 0),
      -(potential_reviewer['scores'].get('similarity') or 0),
      deep_get(potential_reviewer, review_duration_mean_keys, potential_reviewer_mean_duration),
      potential_reviewer['person']['first_name'],
      potential_reviewer['person']['last_name']
    )
  )

  # create a list with interleaving normal reviewer, ecr, ...
  potential_reviewers = [x for x in itertools.chain.from_iterable(itertools.zip_longest(
    (pr for pr in potential_reviewers if not pr['person'].get('is_early_career_researcher')),
    (pr for pr in potential_reviewers if pr['person'].get('is_early_career_researcher'))
  )) if x]
  return potential_reviewers

def sorted_manuscript_scores_descending(manuscript_scores_list):
  return list(reversed(sorted(manuscript_scores_list, key=lambda score: (
    score['combined'],
    score['keyword'],
    score['similarity']
  ))))

def get_reviewer_score(person_keyword_score, best_manuscript_score):
  keyword_score = max(
    person_keyword_score or 0,
    best_manuscript_score.get('keyword', 0)
  )
  similarity_score = best_manuscript_score.get('similarity')
  combined_score = calculate_combined_score(keyword_score, similarity_score)
  return {
    'keyword': keyword_score,
    'similarity': similarity_score,
    'combined': combined_score
  }

def get_person_ids_for_manuscript_list(manuscript_list, person_list_key):
  return set(
    p[PERSON_ID] for p in iter_flatten(
      m[person_list_key] for m in manuscript_list
    )
  )

class RecommendReviewers(object):
  def __init__(
    self, db, manuscript_model, similarity_model=None,
    filter_by_subject_area_enabled=False):

    logger = logging.getLogger(NAME)
    self.logger = logger
    self.similarity_model = similarity_model
    self.filter_by_subject_area_enabled = filter_by_subject_area_enabled

    logger.debug('filter_by_subject_area_enabled: %s', filter_by_subject_area_enabled)

    self.manuscript_versions_all_df = db.manuscript_version.read_frame().reset_index()

    valid_version_ids = manuscript_model.get_valid_manuscript_version_ids()

    self.manuscript_versions_df = filter_by(
      self.manuscript_versions_all_df,
      VERSION_ID,
      valid_version_ids
    )

    logger.debug('loading ManuscriptKeywordService')
    self.manuscript_keyword_service = ManuscriptKeywordService.from_database(
      db, valid_version_ids=valid_version_ids
    )

    logger.debug('loading ManuscriptSubjectAreaService')
    self.manuscript_subject_area_service = ManuscriptSubjectAreaService.from_database(
      db, valid_version_ids=valid_version_ids
    )

    logger.debug('loading ManuscriptPersonRelationshipService')
    self.manuscript_person_relationship_service = ManuscriptPersonRelationshipService(db)

    logger.debug('loading ManuscriptPersonStageService')
    self.manuscript_person_stage_service = ManuscriptPersonStageService(db)

    logger.debug('loading PersonKeywordService')
    self.person_keyword_service = PersonKeywordService.from_database(db)

    logger.debug('loading other manuscript related data')

    self.authors_all_df = (
      db.manuscript_author.read_frame().reset_index()
    )

    self.editors_all_df = (
      db.manuscript_editor.read_frame().reset_index()
    )

    self.senior_editors_all_df = (
      db.manuscript_senior_editor.read_frame().reset_index()
    )

    self.manuscript_history_all_df = (
      db.manuscript_stage.read_frame().reset_index()
    )

    self.manuscript_history_df = filter_by(
      self.manuscript_history_all_df,
      VERSION_ID,
      valid_version_ids
    )

    manuscripts_df = db.manuscript.read_frame().reset_index()

    self.persons_df = db.person.read_frame().reset_index()

    memberships_df = db.person_membership.read_frame()

    dates_not_available_df = db.person_dates_not_available.read_frame().reset_index()

    dates_not_available_df = dates_not_available_df[
      dates_not_available_df['end_date'] >= pd.to_datetime('today')
    ]

    self.manuscript_history_review_received_df = filter_by(
      self.manuscript_history_df,
      'stage_name',
      ['Review Received']
    )

    self.assigned_reviewers_df = db.manuscript_potential_reviewer.read_frame().reset_index()

    temp_memberships_map = groupby_column_to_dict(memberships_df, PERSON_ID)
    dates_not_available_map = groupby_column_to_dict(dates_not_available_df, PERSON_ID)
    # early_career_researchers_person_ids = set(early_career_researchers_df[PERSON_ID].values)

    logger.debug("gathering stats")
    overall_stats_map = stats_by_person_for_period(db.person_review_stats_overall)
    last12m_stats_map = stats_by_person_for_period(db.person_review_stats_last12m)

    logger.debug("building person map")
    self.persons_map = {
      person[PERSON_ID]: {
        **person,
        'memberships': temp_memberships_map.get(person[PERSON_ID], []),
        'dates_not_available': dates_not_available_map.get(person[PERSON_ID], []),
        'stats': {
          'overall': overall_stats_map.get(person[PERSON_ID], None),
          'last_12m': last12m_stats_map.get(person[PERSON_ID], None)
        }
      } for person in clean_result(self.persons_df[PERSON_COLUMNS].to_dict(orient='records'))
    }

    debugv("self.persons_df: %s", self.persons_df)
    debugv("persons_map: %s", self.persons_map)

    logger.debug("building temp author etc. maps")
    temp_authors_map = groupby_column_to_dict(
      self.authors_all_df,
      VERSION_ID,
      lambda author: {
        **self.persons_map.get(author[PERSON_ID], None),
        'is_corresponding_author': author['is_corresponding_author']
      },
      sort_by=[VERSION_ID, 'seq']
    )

    temp_editors_map = groupby_columns_to_dict(
      self.editors_all_df[VERSION_ID].values,
      self.editors_all_df[PERSON_ID].values,
      lambda person_id: self.persons_map.get(person_id, None)
    )

    temp_senior_editors_map = groupby_columns_to_dict(
      self.senior_editors_all_df[VERSION_ID].values,
      self.senior_editors_all_df[PERSON_ID].values,
      lambda person_id: self.persons_map.get(person_id, None)
    )

    temp_reviewers_map = groupby_columns_to_dict(
      self.manuscript_history_review_received_df[VERSION_ID].values,
      self.manuscript_history_review_received_df[PERSON_ID].values,
      lambda person_id: self.persons_map.get(person_id, None)
    )

    logger.debug("building person roles")
    self.person_role_service = PersonRoleService.from_database(db)

    logger.debug("building reviewers by manuscript map")
    self.assigned_reviewers_by_manuscript_id_map = groupby_column_to_dict(
      self.assigned_reviewers_df,
      VERSION_ID,
      lambda row: {
        PERSON_ID: row[PERSON_ID],
        'status': row['status'],
        'excluded': row['suggested_to_exclude'] == 'yes'
      }
    )

    debugv(
      "self.manuscript_history_review_received_df: %s", self.manuscript_history_review_received_df
    )
    debugv("temp_authors_map: %s", temp_authors_map)
    debugv("temp_reviewers_map: %s", temp_reviewers_map)

    logger.debug("building doi by manuscript map")
    temp_doi_by_manuscript_no_map = groupby_column_to_dict(
      manuscripts_df,
      MANUSCRIPT_ID,
      'doi')

    logger.debug("getting all subject areas")
    self.all_subject_areas = sorted(self.manuscript_subject_area_service.get_all_subject_areas())

    logger.debug("getting all keywords")
    self.all_keywords = sorted(
      self.manuscript_keyword_service.get_all_keywords() |
      self.person_keyword_service.get_all_keywords()
    )

    logger.debug("building manuscript list")
    manuscripts_all_list = clean_result(
      self.manuscript_versions_all_df[
        MANUSCRIPT_ID_COLUMNS +
        [MANUSCRIPT_ID] +
        ['title', 'decision', 'manuscript_type', 'abstract', 'decision_timestamp']
      ].rename(columns={'decision-date': 'published-date'})
      .to_dict(orient='records')
    )
    manuscripts_all_list = [
      {
        **manuscript,
        'doi': get_first(temp_doi_by_manuscript_no_map.get(manuscript[MANUSCRIPT_ID], [])),
        'authors': temp_authors_map.get(manuscript[VERSION_ID], []),
        'editors': temp_editors_map.get(manuscript[VERSION_ID], []),
        'senior_editors': temp_senior_editors_map.get(manuscript[VERSION_ID], []),
        'reviewers': temp_reviewers_map.get(manuscript[VERSION_ID], []),
        'subject_areas': (
          self.manuscript_subject_area_service.get_subject_areas_by_id(
            manuscript[VERSION_ID]
          )
        ),
        'is_published': manuscript_model.is_manuscript_published(manuscript)
      } for manuscript in manuscripts_all_list
    ]
    self.manuscripts_by_version_id_map = {
      m[VERSION_ID]: m for m in manuscripts_all_list
    }
    debugv("manuscripts_by_version_id_map: %s", self.manuscripts_by_version_id_map)

    self.manuscripts_by_author_map = {}
    self.manuscripts_by_reviewer_map = {}
    for m in manuscripts_all_list:
      if manuscript_model.is_manuscript_valid(m):
        debugv("manuscript: %s", m)
        # only consider published manuscripts for authors
        if m['is_published']:
          for author in m['authors']:
            self.manuscripts_by_author_map.setdefault(author[PERSON_ID], [])\
            .append(m)
        # also consider not published manuscripts (but valid ones) for reviewers
        for reviewer in m['reviewers']:
          self.manuscripts_by_reviewer_map.setdefault(reviewer[PERSON_ID], [])\
          .append(m)
      else:
        debugv("ignoring manuscript: %s", m)

    remove_duplicate_titles_and_sort_by_date = lambda manuscripts: (
      sort_manuscripts_by_date(duplicate_manuscript_titles_as_alternatives(manuscripts))
    )

    self.manuscripts_by_author_map = applymap_dict(
      self.manuscripts_by_author_map, remove_duplicate_titles_and_sort_by_date
    )

    self.manuscripts_by_reviewer_map = applymap_dict(
      self.manuscripts_by_reviewer_map, remove_duplicate_titles_and_sort_by_date
    )

    debugv("manuscripts_by_author_map: %s", self.manuscripts_by_author_map)
    debugv("manuscripts_by_reviewer_map: %s", self.manuscripts_by_reviewer_map)

    early_career_researcher_person_id_query = db.session.query(
      db.person.table.person_id
    ).filter(
      db.person.table.is_early_career_researcher == True # pylint: disable=C0121
    )

    self.all_early_career_researcher_person_ids = {
      row[0] for row in early_career_researcher_person_id_query.distinct()
    }

    self.early_career_researcher_ids_by_subject_area = groupby_to_dict(
      db.session.query(
        db.person_subject_area.table.subject_area,
        db.person_subject_area.table.person_id
      ).filter(
        db.person_subject_area.table.person_id.in_(
          early_career_researcher_person_id_query
        )
      ).all(),
      lambda row: row[0].lower(),
      lambda row: row[1]
    )
    debugv(
      "early career researcher subject area keys: %s",
      self.early_career_researcher_ids_by_subject_area.keys()
    )

  def __find_manuscripts_by_key(self, manuscript_no):
    return self.manuscript_versions_all_df[
      self.manuscript_versions_all_df[MANUSCRIPT_ID] == manuscript_no
    ].sort_values(VERSION_ID).groupby(MANUSCRIPT_ID).last()

  def _empty_manuscripts(self):
    return self.__find_manuscripts_by_key(None)

  def __parse_keywords(self, keywords):
    keywords = (keywords or '').strip()
    if keywords == '':
      return []
    return [keyword.strip() for keyword in keywords.split(',')]

  def _filter_manuscripts_by_subject_areas(self, manuscripts_df, subject_areas):
    return manuscripts_df[
      manuscripts_df[VERSION_ID].isin(
        self.manuscript_subject_area_service.get_ids_by_subject_areas(subject_areas)
      )
    ]

  def _get_early_career_reviewer_ids_by_subject_areas(self, subject_areas):
    if len(subject_areas) == 0:
      result = self.all_early_career_researcher_person_ids
    else:
      result = set(iter_flatten(
        self.early_career_researcher_ids_by_subject_area.get(subject_area.lower(), [])
        for subject_area in subject_areas
      ))
    self.logger.debug(
      "found %d early career researchers for subject areas: %s", len(result), subject_areas
    )
    return result

  def get_all_subject_areas(self):
    return self.all_subject_areas

  def get_all_keywords(self):
    return self.all_keywords

  def user_has_role_by_email(self, email, role):
    return self.person_role_service.user_has_role_by_email(email=email, role=role)

  def get_user_roles_by_email(self, email):
    return self.person_role_service.get_user_roles_by_email(email=email)

  def recommend(
    self, manuscript_no=None, subject_area=None, keywords=None, abstract=None,
    **kwargs):

    if manuscript_no:
      return self._recommend_using_manuscript_no(
        manuscript_no=manuscript_no,
        **kwargs
      )
    else:
      return self._recommend_using_user_search_criteria(
        subject_area=subject_area, keywords=keywords, abstract=abstract,
        **kwargs
      )

  def _no_manuscripts_found_response(self, manuscript_no):
    return {
      'manuscripts_not_found': [manuscript_no],
      'matching_manuscripts': [],
      'potential_reviewers': []
    }

  def _recommend_using_manuscript_no(self, manuscript_no=None, **kwargs):
    matching_manuscripts = self.__find_manuscripts_by_key(manuscript_no)
    if len(matching_manuscripts) == 0:
      return self._no_manuscripts_found_response(manuscript_no)
    else:
      matching_version_ids = matching_manuscripts[VERSION_ID]
      keyword_list = sorted(self.manuscript_keyword_service.get_keywords_by_ids(
        matching_version_ids
      ))
      matching_manuscripts_dicts = map_to_dict(
        matching_version_ids,
        self.manuscripts_by_version_id_map
      )
      manuscript_subject_areas = set(iter_flatten(
        self.manuscript_subject_area_service.get_subject_areas_by_id(version_id)
        for version_id in matching_version_ids
      ))
      # we search by subject areas for ECRs as there may otherwise not much data
      # available
      ecr_subject_areas = manuscript_subject_areas
      subject_areas = (
        manuscript_subject_areas
        if self.filter_by_subject_area_enabled
        else {}
      )
      assigned_reviewers_by_person_id = groupby_to_dict(
        iter_flatten(
          self.assigned_reviewers_by_manuscript_id_map.get(manuscript_id, [])
          for manuscript_id in matching_manuscripts[VERSION_ID].values
        ),
        lambda item: item[PERSON_ID],
        lambda item: filter_dict_keys(item, lambda key: key != PERSON_ID)
      )
      self.logger.debug("assigned_reviewers_by_person_id: %s", assigned_reviewers_by_person_id)
      self.logger.debug("subject_areas: %s", subject_areas)
      exclude_person_ids = (
        get_person_ids_for_manuscript_list(matching_manuscripts_dicts, 'authors') |
        get_person_ids_for_manuscript_list(matching_manuscripts_dicts, 'editors') |
        get_person_ids_for_manuscript_list(matching_manuscripts_dicts, 'senior_editors')
      )
      return {
        **self._recommend_using_criteria(
          subject_areas=subject_areas,
          keyword_list=keyword_list,
          include_person_ids=assigned_reviewers_by_person_id.keys(),
          exclude_person_ids=exclude_person_ids,
          ecr_subject_areas=ecr_subject_areas,
          manuscript_version_ids=matching_manuscripts[VERSION_ID].values,
          **kwargs
        ),
        'matching_manuscripts': clean_manuscripts(map_to_dict(
          matching_manuscripts[VERSION_ID],
          self.manuscripts_by_version_id_map
        ))
      }

  def _recommend_using_user_search_criteria(
    self, subject_area=None, keywords=None, abstract=None, **kwargs):

    subject_areas = (
      {subject_area}
      if subject_area is not None and len(subject_area) > 0
      else {}
    )
    keyword_list = self.__parse_keywords(keywords)
    return {
      **self._recommend_using_criteria(
        subject_areas=subject_areas, keyword_list=keyword_list, abstract=abstract,
        **kwargs
      ),
      'search': remove_none({
        'subject_areas': subject_areas,
        'keywords': keyword_list,
        'abstract': abstract
      })
    }

  def _populate_potential_reviewer(
    self, person_id,
    version_ids,
    keyword_score_by_person_id,
    manuscript_score_by_id):

    scores_by_manuscript = sorted_manuscript_scores_descending(
      score for score in (
        manuscript_score_by_id.get(version_id)
        for version_id in version_ids
      ) if score
    )

    best_score = get_first(scores_by_manuscript, {})
    reviewer_score = get_reviewer_score(
      person_keyword_score=keyword_score_by_person_id.get(person_id),
      best_manuscript_score=best_score
    )

    author_of_manuscripts = self.manuscripts_by_author_map.get(person_id, [])
    author_of_manuscript_ids = set(m[VERSION_ID] for m in author_of_manuscripts)

    potential_reviewer = {
      'person': self.persons_map.get(person_id, None),
      'author_of_manuscripts': clean_manuscripts(author_of_manuscripts),
      'scores': {
        **reviewer_score,
        'by_manuscript': [
          m
          for m in scores_by_manuscript
          if m[VERSION_ID] in author_of_manuscript_ids
        ]
      }
    }
    if potential_reviewer.get('person') is None:
      self.logger.warning('person id not found: %s', person_id)
      debugv('valid persons: %s', self.persons_map.keys())
    return potential_reviewer

  def _populate_potential_reviewers(
    self, person_ids, person_ids_by_version_id,
    keyword_score_by_person_id,
    keyword_score_by_version_id, similarity_by_manuscript_version_id):

    manuscript_score_by_id = self._combine_manuscript_scores_by_id(
      keyword_score_by_version_id=keyword_score_by_version_id,
      similarity_by_manuscript_version_id=similarity_by_manuscript_version_id
    )

    version_ids_by_person_id = invert_set_dict(person_ids_by_version_id)

    return (
      self._populate_potential_reviewer(
        person_id,
        version_ids=version_ids_by_person_id.get(person_id, set()),
        keyword_score_by_person_id=keyword_score_by_person_id,
        manuscript_score_by_id=manuscript_score_by_id
      )
      for person_id in person_ids
    )

  def _find_manuscript_ids_by_subject_areas_and_keywords_with_keyword_scores(
    self, subject_areas, keyword_list):

    self.logger.debug("keyword_list: %s", keyword_list)
    self.logger.debug("subject_areas: %s", subject_areas)

    if keyword_list:
      keyword_score_by_version_id = self.manuscript_keyword_service.get_keyword_scores(keyword_list)
      version_ids = keyword_score_by_version_id.keys()
      if subject_areas and version_ids:
        version_ids = version_ids & self.manuscript_subject_area_service.get_ids_by_subject_areas(
          subject_areas
        )
      return version_ids, keyword_score_by_version_id
    elif subject_areas:
      version_ids = self.manuscript_subject_area_service.get_ids_by_subject_areas(subject_areas)
      return version_ids, {}
    else:
      return set(), {}

  def _find_most_similar_manuscript_ids_with_scores(
    self, subject_areas=None, abstract=None, manuscript_version_ids=None,
    similarity_threshold=0.5, max_similarity_count=50):

    if abstract is not None and len(abstract.strip()) > 0:
      all_similar_manuscripts = self.similarity_model.find_similar_manuscripts_to_abstract(
        abstract
      )
    else:
      all_similar_manuscripts = self.similarity_model.find_similar_manuscripts(
        manuscript_version_ids or set()
      )
    self.logger.debug("all_similar_manuscripts: %d", len(all_similar_manuscripts))
    similar_manuscripts = all_similar_manuscripts
    if subject_areas:
      similar_manuscripts = self._filter_manuscripts_by_subject_areas(
        similar_manuscripts, subject_areas
      )
    most_similar_manuscripts = similar_manuscripts[
      similar_manuscripts[SIMILARITY_COLUMN] >= similarity_threshold
    ]
    self.logger.debug(
      "found %d/%d similar manuscripts beyond threshold %f",
      len(most_similar_manuscripts),
      len(similar_manuscripts),
      similarity_threshold
    )
    if len(most_similar_manuscripts) > max_similarity_count:
      most_similar_manuscripts = most_similar_manuscripts\
      .sort_values(SIMILARITY_COLUMN, ascending=False)[:max_similarity_count]

    # Here we are including all manuscripts we calculated the similarity for in case they
    # are included due to their better keyword match
    similarity_by_manuscript_version_id = (
      all_similar_manuscripts.set_index(VERSION_ID)[SIMILARITY_COLUMN].to_dict()
    )

    return most_similar_manuscripts[VERSION_ID].values, similarity_by_manuscript_version_id

  def _find_matching_manuscript_ids_with_scores(
    self, subject_areas=None, keyword_list=None, abstract=None,
    manuscript_version_ids=None):

    keyword_matching_manuscript_ids, keyword_score_by_version_id = (
      self._find_manuscript_ids_by_subject_areas_and_keywords_with_keyword_scores(
        subject_areas, keyword_list
      )
    )

    most_similar_manuscript_ids, similarity_by_manuscript_version_id = (
      self._find_most_similar_manuscript_ids_with_scores(
        subject_areas=subject_areas,
        abstract=abstract,
        manuscript_version_ids=manuscript_version_ids
      )
    )

    matching_manuscript_ids = set(keyword_matching_manuscript_ids) | set(most_similar_manuscript_ids)

    return (
      matching_manuscript_ids,
      keyword_score_by_version_id,
      similarity_by_manuscript_version_id
    )

  def _combine_manuscript_scores_by_id(
    self, keyword_score_by_version_id, similarity_by_manuscript_version_id):

    return {
      version_id: score_by_manuscript(
        {VERSION_ID: version_id},
        keyword=keyword_score_by_version_id.get(version_id, 0),
        similarity=similarity_by_manuscript_version_id.get(version_id, None)
      )
      for version_id in keyword_score_by_version_id.keys() | similarity_by_manuscript_version_id.keys()
    }

  def _filter_published_version_ids(self, version_ids):
    return {
      version_id for version_id in version_ids
      if self.manuscripts_by_version_id_map.get(version_id, {}).get('is_published')
    }

  def _potential_reviewer_ids_by_matching_manuscript_ids(
    self, version_ids,
    recommend_relationship_types, recommend_stage_names):

    published_version_ids = self._filter_published_version_ids(version_ids)
    person_ids_by_relationship_types = (
      self.manuscript_person_relationship_service
      .get_person_ids_by_version_id_for_relationship_types(
        published_version_ids, # recommend only published manuscripts by relationship type
        recommend_relationship_types
      )
    )
    person_ids_by_stage_names = (
      self.manuscript_person_stage_service
      .get_person_ids_by_version_id_for_stage_names(
        version_ids, # recommend also unpublished by stage name
        recommend_stage_names
      )
    )
    result = {
      version_id: (
        person_ids_by_relationship_types.get(version_id, set()) |
        person_ids_by_stage_names.get(version_id, set())
      )
      for version_id in version_ids
    }
    count_values = lambda d: sum(len(x) for x in d.values())
    self.logger.debug(
      'person_ids for version ids=%d stage names=%d (%s),'
      ' published version ids=%d by relationship types=%d (%s), total=%d (counts overlap)',
      len(version_ids),
      count_values(person_ids_by_stage_names), recommend_stage_names,
      len(published_version_ids),
      count_values(person_ids_by_relationship_types), recommend_relationship_types,
      count_values(result)
    )
    return result

  def _find_potential_reviewer_ids(
    self, person_ids_by_version_id,
    include_person_ids, exclude_person_ids, ecr_subject_areas,
    person_keyword_scores, role):

    return self.person_role_service.filter_person_ids_by_role(
      (
        set(iter_flatten(person_ids_by_version_id.values())) |
        get_person_ids_of_person_keywords_scores(person_keyword_scores) |
        self._get_early_career_reviewer_ids_by_subject_areas(ecr_subject_areas) |
        include_person_ids
      ) - exclude_person_ids,
      role=role
    )

  def _recommend_using_criteria(
    self, subject_areas=None, keyword_list=None, abstract=None,
    include_person_ids=None, exclude_person_ids=None, ecr_subject_areas=None,
    manuscript_version_ids=None,
    role=None,
    recommend_relationship_types=None, recommend_stage_names=None,
    limit=None):

    if recommend_relationship_types is None:
      recommend_relationship_types = [RelationshipTypes.AUTHOR]
    if recommend_stage_names is None:
      recommend_stage_names = [StageNames.REVIEW_RECEIVED]

    include_person_ids = include_person_ids or set()
    exclude_person_ids = exclude_person_ids or set()
    subject_areas = subject_areas or set()
    if ecr_subject_areas is None:
      ecr_subject_areas = subject_areas

    matching_manuscript_ids, keyword_score_by_version_id, similarity_by_manuscript_version_id = (
      self._find_matching_manuscript_ids_with_scores(
        subject_areas=subject_areas, keyword_list=keyword_list, abstract=abstract,
        manuscript_version_ids=manuscript_version_ids
      )
    )

    person_ids_by_version_id = self._potential_reviewer_ids_by_matching_manuscript_ids(
      matching_manuscript_ids,
      recommend_relationship_types=recommend_relationship_types,
      recommend_stage_names=recommend_stage_names
    )

    person_keyword_scores = self.person_keyword_service.get_keyword_scores(keyword_list)

    potential_reviewers_ids = self._find_potential_reviewer_ids(
      person_ids_by_version_id=person_ids_by_version_id,
      include_person_ids=include_person_ids,
      exclude_person_ids=exclude_person_ids,
      ecr_subject_areas=ecr_subject_areas,
      person_keyword_scores=person_keyword_scores,
      role=role
    )

    potential_reviewers = sorted_potential_reviewers(
      self._populate_potential_reviewers(
        potential_reviewers_ids,
        person_ids_by_version_id=person_ids_by_version_id,
        keyword_score_by_person_id=person_keyword_scores,
        keyword_score_by_version_id=keyword_score_by_version_id,
        similarity_by_manuscript_version_id=similarity_by_manuscript_version_id
      )
    )

    if limit is not None and limit > 0:
      potential_reviewers = potential_reviewers[:limit]

    result = {
      'potential_reviewers': potential_reviewers
    }
    return result
