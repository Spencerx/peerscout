import React from 'react';
import More from 'react-more';

import {
  Card,
  CardActions,
  CardHeader,
  CardText,
  Chip,
  Comment,
  FlatButton,
  FlexColumn,
  FontAwesomeIcon,
  InlineContainer,
  Link,
  RaisedButton,
  Text,
  TooltipWrapper,
  View
} from '../../components';

import { groupBy } from '../../utils';

import ManuscriptTooltipContent from './ManuscriptTooltipContent';

import {
  formatCombinedScore,
  formatScoreWithDetails
} from './formatUtils';

const commonStyles = {
  link: {
    textDecoration: 'none',
    cursor: 'hand'
  }
};

const LABEL_WIDTH = 105;

const styles = {
  card: {
    marginBottom: 20
  },
  stats: {
    container: {
    },
    label: {
      display: 'inline-block',
      minWidth: LABEL_WIDTH,
      fontWeight: 'bold'
    },
    value: {
      display: 'inline-block',
      textAlign: 'right',
      minWidth: 100
    }
  },
  potentialReviewer: {
    container: {
      fontSize: 20,
      padding: 5,
      borderWidth: 1,
      borderColor: '#eee',
      borderStyle: 'solid',
      margin: 3
    },
    card: {
      marginBottom: 10,
    },
    subSection: {
      marginBottom: 5,
      display: 'flex',
      flexDirection: 'row'
    },
    label: {
      display: 'inline-block',
      minWidth: LABEL_WIDTH,
      fontWeight: 'bold'
    },
    value: {
      flex: 1
    }
  },
  manuscriptSummary: {
    container: {
      marginBottom: 10,
    },
    text: {
      fontSize: 20,
      fontWeight: 'bold'
    },
    subSection: {
      marginBottom: 5,
      marginLeft: LABEL_WIDTH
    },
    label: {
      display: 'inline-block',
      minWidth: LABEL_WIDTH,
      fontWeight: 'bold',
      marginLeft: -LABEL_WIDTH
    },
    abstractSubSection: {
      marginBottom: 5
    },
    abstractLabel: {
      display: 'inline-block',
      minWidth: 100,
      fontWeight: 'bold'
    }
  },
  inlineContainer: {
    display: 'inline-block'
  },
  inlineNonBlock: {
    display: 'inline'
  },
  unrecognisedMembership: {
    display: 'inline-block',
    marginLeft: 10
  },
  emailLink: {
    ...commonStyles.link,
    display: 'inline-block',
    marginLeft: 10
  },
  correspondingAuthorIndicator: {
    ...commonStyles.link,
    display: 'inline-block',
    marginLeft: 5
  },
  membershipLink: {
    ...commonStyles.link,
    display: 'inline-block',
    marginLeft: 10
  },
  manuscriptInlineSummary: {
    matchingSubjectAreas: {
      display: 'inline-block'
    },
    notMatchingSubjectAreas: {
      display: 'inline-block',
      color: '#888'
    }
  },
  errorMessage: {
    padding: 20,
    fontSize: 20,
    color: '#f22'
  },
  buttons: {
    padding: 10
  }
};

const formatPersonStatus = status =>
  status && status.length > 0 ? status : 'Unknown status';

const combinedPersonName = person =>
  [
    person['title'],
    person['first_name'],
    person['middle_name'],
    person['last_name'],
    person['is_early_career_researcher'] ? '(early career reviewer)': undefined,
    person['status'] !== 'Active' && `(${formatPersonStatus(person['status'])})`
  ].filter(s => !!s).join(' ');

const quote = s => s && `\u201c${s}\u201d`

const formatManuscriptId = manuscript => manuscript['manuscript_id'];

const doiUrl = doi => doi && 'http://dx.doi.org/' + doi;

const hasMatchingSubjectAreas = (manuscript, requestedSubjectAreas) =>
  requestedSubjectAreas.length === 0 || !!(manuscript['subject_areas'] || []).filter(
    subjectArea => requestedSubjectAreas.has(subjectArea)
  )[0];

const NBSP = '\xa0';

const Score = ({ score = {} }) => (
  <Text
    className="score"
    title={ (score.combined && formatScoreWithDetails(score)) || '' }
  >{ (score.combined && formatCombinedScore(score.combined)) || NBSP }</Text>
);

const PersonScore = ({ score, person }) => (
  <InlineContainer
    className={
      person.is_early_career_researcher ?
      'person-score early-career-researcher-score' :
      'person-score'
    }
  >
    <Score score={ score }/>
  </InlineContainer>
);

const ManuscriptRefLink = ({ manuscript }) => (
  <Link
    style={ styles.manuscriptLink }
    target="_blank"
    href={ doiUrl(manuscript['doi']) }
  >
    <Text>{ formatManuscriptId(manuscript) }</Text>
  </Link>
);

const ManuscriptRefLinkWithAlternatives = ({ manuscript }) => (
  <InlineContainer>
    <ManuscriptRefLink manuscript={ manuscript }/>
    {
      manuscript.alternatives && manuscript.alternatives.map(alternative =>
        (
          <InlineContainer>
            <Text>{ ', ' }</Text>
            <ManuscriptRefLink manuscript={ alternative }/>
          </InlineContainer>
        )
      )
    }
  </InlineContainer>
);

const ManuscriptInlineSummary = ({ manuscript, scores = {}, requestedSubjectAreas }) => {
  return (
    <View
      style={
        hasMatchingSubjectAreas(manuscript, requestedSubjectAreas) ?
        styles.manuscriptInlineSummary.matchingSubjectAreas :
        styles.manuscriptInlineSummary.notMatchingSubjectAreas
      }
    >
      <TooltipWrapper content={ <ManuscriptTooltipContent manuscript={ manuscript}/> } style={ styles.inlineContainer }>
        <Text>{ quote(manuscript['title']) }</Text>
      </TooltipWrapper>
      <Text>{ ' ' }</Text>
      <Text>{ formatDate(manuscript['published_date']) }</Text>
      <Text>{ ' (' }</Text>
      <ManuscriptRefLinkWithAlternatives manuscript={ manuscript }/>
      <Text>{ ') ' }</Text>
      {
        scores.combined && (
          <InlineContainer>
            <Text>{ '- ' }</Text>
            <Score score={ scores }/>
          </InlineContainer>
        ) || null
      }
    </View>
  );
};

const PersonEmailLink = ({ person: { email } }) => (
  <Link
    style={ styles.emailLink }
    target="_blank"
    href={ `mailto:${email}` }
  >
    <Text>{ email }</Text>
  </Link>
);

const CorrespondingAuthorIndicator = ({ person: { email } }) => {
  if (email) {
    return (
      <Link
        style={ styles.correspondingAuthorIndicator }
        target="_blank"
        href={ `mailto:${email}` }
        title={ email }
      >
        <FontAwesomeIcon name="envelope"/>
      </Link>
    );
  } else {
    return (
      <View style={ styles.correspondingAuthorIndicator }>
        <FontAwesomeIcon name="envelope"/>
      </View>
    );
  }
};

const PersonInlineSummary = ({ person }) => (
  <Text>{ combinedPersonName(person) }</Text>
);

const PersonListInlineSummary = ({ persons }) => (
  <View style={ styles.inlineNonBlock }>
    {
      persons && persons.map((person, index) => (
        <View key={ index } style={ styles.inlineNonBlock }>
          {
            index > 0 && (
              <Text>{ ', ' }</Text>
            )
          }
          <PersonInlineSummary person={ person }/>
          {
            person.is_corresponding_author && (
              <CorrespondingAuthorIndicator person={ person }/>
            )
          }
        </View>
      ))
    }
  </View>
);

const Membership = ({ membership }) => {
  if (membership['member_type'] != 'ORCID') {
    return (
      <Text style={ styles.unrecognisedMembership }>
        { `${membership['member_type']}: ${membership['member_id']}` }
      </Text>
    );
  }
  return (
    <View style={ styles.inlineContainer }>
      <Link
        style={ styles.membershipLink }
        target="_blank"
        href={ `http://orcid.org/${membership['member_id']}` }
      >
        <Text>ORCID</Text>
      </Link>
      <Link
        style={ styles.membershipLink }
        target="_blank"
        href={ `http://search.crossref.org/?q=${membership['member_id']}` }
      >
        <Text>Crossref</Text>
      </Link>
    </View>
  );
};

const personFullName = person => [
  person['first_name'],
  person['middle_name'],
  person['last_name']
].filter(s => !!s).join(' ');

const PersonWebSearchLink = ({ person }) => (
  <Link
    style={ styles.membershipLink }
    target="_blank"
    href={ `http://search.crossref.org/?q=${encodeURIComponent(personFullName(person))}` }
  >
    <Text><FontAwesomeIcon name="search"/></Text>
  </Link>
);

const formatDate = date => date && new Date(date).toLocaleDateString();

const formatPeriodNotAvailable = periodNotAvailable =>
  `${formatDate(periodNotAvailable['start_date'])} - ${formatDate(periodNotAvailable['end_date'])}`;

const formatCount = (count, singular, plural, suffix) =>
  (count !== undefined) && `${count} ${count === 1 ? singular : plural} ${suffix || ''}`.trim();

const formatDays = days =>
  (days !== undefined) && `${days.toFixed(1)} ${days === 1.0 ? 'day' : 'days'}`;

const formatPeriodStats = periodStats => {
  const {
    mean,
    count
  } = periodStats['review_duration'] || {};
  return [
    mean && `${formatDays(mean)} (avg over ${formatCount(count, 'review', 'reviews')})`,
    formatCount(periodStats['reviews_in_progress'], 'review', 'reviews', 'in progress'),
    formatCount(periodStats['waiting_to_be_accepted'], 'review', 'reviews', 'awaiting response'),
    formatCount(periodStats['declined'], 'review', 'reviews', 'declined')
  ].filter(s => !!s).join(', ');
}

const renderStats = stats => {
  const overallStats = formatPeriodStats((stats || {})['overall'] || {});
  const last12mStats = formatPeriodStats((stats || {})['last_12m'] || {});
  if (!overallStats && !last12mStats) {
    return;
  }
  return (
    <FlexColumn>
      {
        <View>
          <Text>{ 'Overall: ' }</Text>
          <Text>{ overallStats }</Text>
        </View>
      }
      {
        <View>
          <Text>{ 'Last 12 months: ' }</Text>
          <Text>{ last12mStats === overallStats ? 'see above' : last12mStats || 'n/a' }</Text>
        </View>
      }
    </FlexColumn>
  );
};

const formatAssignmentStatus = assignmentStatus => assignmentStatus && assignmentStatus.toLowerCase();

const PotentialReviewer = ({
  potentialReviewer,
  requestedSubjectAreas,
  onSelectPotentialReviewer  
}) => {
  const {
    person = {},
    author_of_manuscripts: authorOfManuscripts = [],
    reviewer_of_manuscripts: reviewerOfManuscripts = [],
    assignment_status: assignmentStatus,
    scores
  } = potentialReviewer;
  const onSelectThisPotentialReviewer = () => {
    if (onSelectPotentialReviewer) {
      onSelectPotentialReviewer(potentialReviewer);
    }
  };
  const manuscriptScoresByManuscriptNo = groupBy(scores['by_manuscript'] || [], s => s['manuscript_id']);
  const memberships = person.memberships || [];
  const membershipComponents = memberships.map((membership, index) => (
    <Membership key={ index } membership={ membership }/>
  ));
  if (membershipComponents.length === 0) {
    membershipComponents.push((<PersonWebSearchLink key="search" person={ person }/>));
  }
  const titleComponent = (
    <View style={ styles.inlineContainer }>
      <Text onClick={ onSelectThisPotentialReviewer }>{ combinedPersonName(person) }</Text>
      {
        assignmentStatus && (
          <Text style={ styles.assignmentStatus }>
            { ` (${formatAssignmentStatus(assignmentStatus['status'])})` }
          </Text>
        )
      }
      { membershipComponents }
    </View>
  );
  const subtitleComponent = (
    <View style={ styles.inlineContainer }>
      <Text>{ person['institution'] }</Text>
      {
        person['email'] && (
          <PersonEmailLink person={ person } />
        )
      }
    </View>
  );
  const renderManuscripts = manuscripts => manuscripts && manuscripts.map((manuscript, index) => (
    <ManuscriptInlineSummary
      key={ index }
      manuscript={ manuscript }
      scores={ manuscriptScoresByManuscriptNo[manuscript['manuscript_id']] }
      requestedSubjectAreas={ requestedSubjectAreas }
    />
  ));
  const renderedStats = renderStats(person['stats']);
  const scoresNote = scores && scores.combined ?
    ' (max across manuscripts)' :
    ' Not enough data to calculate a score';
  return (
    <Card style={ styles.potentialReviewer.card }>
      <Comment text={ `Person id: ${person['person_id']}` }/>
      <CardHeader
        title={ titleComponent }
        subtitle={ subtitleComponent }
      />
      <CardText>
        {
          person['dates_not_available'] && person['dates_not_available'].length > 0 && (
            <View style={ styles.potentialReviewer.subSection }>
              <Text style={ styles.potentialReviewer.label }>Not Available: </Text>
              <Text style={ styles.potentialReviewer.value }>
                { person['dates_not_available'].map(formatPeriodNotAvailable).join(', ') }
              </Text>
            </View>
          )
        }
        {
          renderedStats && (
            <View style={ styles.potentialReviewer.subSection }>
              <Text style={ styles.potentialReviewer.label }>Review Time: </Text>
              <View style={ styles.potentialReviewer.value }>
                { renderedStats }
              </View>
            </View>
          )
        }
        {
          (authorOfManuscripts.length > 0) && (
            <View
              style={ styles.potentialReviewer.subSection }
              className="potential_reviewer_author_of"
            >
              <Text style={ styles.potentialReviewer.label }>Author of: </Text>
              <View style={ styles.potentialReviewer.value }>
                <More lines={ 5 }>
                  <FlexColumn>
                    { renderManuscripts(authorOfManuscripts) }
                  </FlexColumn>
                </More>
              </View>
            </View>
          )
        }
        {
          (reviewerOfManuscripts.length > 0) && (
            <View
              style={ styles.potentialReviewer.subSection }
              className="potential_reviewer_reviewer_of"
            >
              <Text style={ styles.potentialReviewer.label }>Reviewer of: </Text>
              <View style={ styles.potentialReviewer.value }>
                <More lines={ 5 }>
                  <FlexColumn>
                    { renderManuscripts(reviewerOfManuscripts) }
                  </FlexColumn>
                </More>
              </View>
            </View>
          )
        }
        <View  style={ styles.potentialReviewer.subSection }>
          <Text style={ styles.potentialReviewer.label }>Scores: </Text>
          <View style={ styles.potentialReviewer.value }>
            <FlexColumn>
              <InlineContainer onClick={ onSelectThisPotentialReviewer }>
                <PersonScore score={ scores } person={ person }/>
                <Text>{ scoresNote }</Text>
              </InlineContainer>
            </FlexColumn>
          </View>
        </View>
      </CardText>
    </Card>
  );
};


const ManuscriptSummary = ({ manuscript }) => {
  const {
    title,
    'manuscript_id': manuscriptNo,
    abstract,
    authors,
    reviewers,
    editors,
    'senior_editors': seniorEditors,
    'subject_areas': subjectAreas
  } = manuscript;
  return (
    <Card style={ styles.manuscriptSummary.container } initiallyExpanded={ true }>
      <CardHeader
        title={ quote(title) }
        subtitle={ <ManuscriptRefLink manuscript={ manuscript }/> }
        actAsExpander={ true }
        showExpandableButton={ true }
      />
      <CardText>
        <View style={ styles.manuscriptSummary.subSection }>
          <Text style={ styles.manuscriptSummary.label }>Authors: </Text>
          <PersonListInlineSummary persons={ authors }/>
        </View>
        {
          reviewers && reviewers.length > 0 && (
            <View  style={ styles.manuscriptSummary.subSection }>
              <Text style={ styles.manuscriptSummary.label }>Reviewers: </Text>
              <PersonListInlineSummary persons={ reviewers }/>
            </View>
          )
        }
        {
          editors && editors.length > 0 && (
            <View  style={ styles.manuscriptSummary.subSection }>
              <Text style={ styles.manuscriptSummary.label }>Editors: </Text>
              <PersonListInlineSummary persons={ editors }/>
            </View>
          )
        }
        {
          seniorEditors && seniorEditors.length > 0 && (
            <View  style={ styles.manuscriptSummary.subSection }>
              <Text style={ styles.manuscriptSummary.label }>Senior Editors: </Text>
              <PersonListInlineSummary persons={ seniorEditors }/>
            </View>
          )
        }
      </CardText>
      <CardText expandable={ true }>
        <View  style={ styles.manuscriptSummary.subSection }>
          <Text style={ styles.manuscriptSummary.label }>Subject areas:</Text>
          <Text>{ subjectAreas.join(', ') }</Text>
        </View>
        <View  style={ styles.manuscriptSummary.abstractSubSection }>
          <FlexColumn>
            <Text style={ styles.manuscriptSummary.abstractLabel }>Abstract:</Text>
            <Text>{ quote(abstract) }</Text>
          </FlexColumn>
        </View>
      </CardText>
    </Card>
  );
};


const extractAllSubjectAreas = manuscripts => {
  const subjectAreas = new Set();
  if (manuscripts) {
    manuscripts.forEach(m => {
      (m['subject_areas'] || []).forEach(subjectArea => {
        subjectAreas.add(subjectArea);
      })
    });
  };
  return subjectAreas;
}

const filterReviewsByEarlyCareerResearcherStatus = (potentialReviewers, earlyCareerReviewer) =>
  potentialReviewers.filter(potentialReviewer =>
    potentialReviewer.person['is_early_career_researcher'] === earlyCareerReviewer
  );

const reviewerPersonId = reviewer => reviewer && reviewer.person && reviewer.person['person_id'];

const SearchResult = ({
  searchResult,
  selectedReviewer,
  selectedManuscript,
  onClearSelection,
  onSelectPotentialReviewer
}) => {
  const {
    potentialReviewers = [],
    matchingManuscripts = [],
    manuscriptsNotFound,
    notAuthorized,
    error
  } = searchResult;
  const requestedSubjectAreas = extractAllSubjectAreas(matchingManuscripts);
  const hasManuscriptsNotFound = manuscriptsNotFound && manuscriptsNotFound.length > 0;
  const filteredPotentialReviewers =
    selectedManuscript ? [] : (
      !selectedReviewer ? potentialReviewers :
      potentialReviewers.filter(r => reviewerPersonId(r) === reviewerPersonId(selectedReviewer))
    );
  const nonEmptySelection = selectedReviewer || selectedManuscript;
  const errorMessage = error && (
    notAuthorized ? 'You are not authorized to see the results.' :
    'This is very unfortunate, but there seems to be some sort of technical issue. Have you tried turning it off and on again?'
  );
  return (
    <View className="result-list">
      {
        errorMessage && (
          <View style={ styles.errorMessage }>
            <Text>
              { errorMessage }
            </Text>
          </View>
        )
      }
      {
        hasManuscriptsNotFound && (
          <View style={ styles.errorMessage }>
            <Text>{ `Manuscript not found: ${manuscriptsNotFound.join(', ')}` }</Text>
          </View>
        )
      }
      {
        !nonEmptySelection && matchingManuscripts.map((matchingManuscript, index) => (
          <ManuscriptSummary
            key={ index }
            manuscript={ matchingManuscript }
          />
        ))
      }
      {
        selectedManuscript && (
          <ManuscriptSummary
            manuscript={ selectedManuscript }
          />
        )
      }
      {
        filteredPotentialReviewers.map((potentialReviewer, index) => (
          <PotentialReviewer
            key={ index }
            potentialReviewer={ potentialReviewer }
            requestedSubjectAreas={ requestedSubjectAreas }
            onSelectPotentialReviewer={ onSelectPotentialReviewer }
          />
        ))
      }
      {
        !hasManuscriptsNotFound && !error && potentialReviewers.length === 0 && (
          <View style={ styles.errorMessage }>
            <Text>{ 'No potential reviewers found' }</Text>
          </View>
        )
      }
      {
        nonEmptySelection && (
          <View style={ styles.buttons }>
            <RaisedButton
              primary={ true }
              onClick={ onClearSelection }
              label="Clear Selection"
            />
          </View>
        )
      }
    </View>
  );
};

export default SearchResult;
