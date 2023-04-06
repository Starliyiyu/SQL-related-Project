
SET search_path TO election;


-- revoke & grant statements for 1.

REVOKE ALL ON Campaign, Donors, Donations, Workers, CampaignActivity,
                CampaignWorkers, ActivityWorkers, Debates, DebateCandidates
                FROM liyiyu1;

GRANT SELECT (cid, amount, donorEmail) ON Donations TO liyiyu1;
GRANT SELECT (donorEmail, donorType) ON Donors TO liyiyu1;
GRANT SELECT (cid) ON Campaign TO liyiyu1;


-- 1. List total organizational donations and total individual
--    donations for each campaign.

CREATE OR REPLACE VIEW organizationDonationPerCampaign AS
SELECT cid, sum(amount) AS organizational_donations
FROM Donors JOIN Donations USING (donorEmail)
WHERE donorType = 'organization'
GROUP BY cid;

CREATE OR REPLACE VIEW individualDonationPerCampaign AS
SELECT cid, sum(amount) AS individual_donations
FROM Donors JOIN Donations USING (donorEmail)
WHERE donorType = 'individual'
GROUP BY cid;

SELECT cid, COALESCE(organizational_donations, 0) AS organizational_donations, 
                COALESCE(individual_donations, 0) AS individual_donations
FROM organizationDonationPerCampaign FULL JOIN individualDonationPerCampaign
                        USING (cid) FULL JOIN (SELECT cid FROM Campaign) temp
                        USING (cid) ORDER BY cid;


-- revoke & grant statements for 2.

REVOKE ALL ON Campaign, Donors, Donations, Workers, CampaignActivity,
                CampaignWorkers, ActivityWorkers, Debates, DebateCandidates
                FROM liyiyu1;

GRANT SELECT (cid) ON Campaign TO liyiyu1;
GRANT SELECT (email, workerType) ON Workers TO liyiyu1;
GRANT SELECT (cid, email) ON CampaignWorkers TO liyiyu1;
GRANT SELECT (email) ON ActivityWorkers TO liyiyu1;

-- 2. Find those volunteers who offer to work on every campaign in the dataset.
-- ccc should not be in the result, aaa & bbb should be in the result

CREATE OR REPLACE VIEW ideal AS -- ideal situation where every volunteer has
                                -- offered to work for every campaign
SELECT * FROM
(SELECT cid FROM Campaign) c1 -- all unique campaign IDs, cid is a primary key
CROSS JOIN 
(SELECT email 
FROM Workers JOIN CampaignWorkers USING (email)
WHERE workerType = 'volunteer') c2; -- all unique volunteer emails
                                 -- (of whom has offered to work for
                                 -- at least 1 campaign)

CREATE OR REPLACE VIEW actual AS -- actual situation of volunteer-campaign pairs
SELECT DISTINCT cid, email
FROM ActivityWorkers JOIN CampaignWorkers USING (email)
        JOIN Workers USING (email)
WHERE workerType = 'volunteer';

CREATE OR REPLACE VIEW notAll AS -- email-cid pairs of volunteers who
                                 -- have not offered to work for 
                                 -- every campaign
(SELECT cid, email FROM ideal)
EXCEPT
(SELECT cid, email FROM actual);


(SELECT email FROM actual)
EXCEPT 
(SELECT email FROM notAll)
ORDER BY email;

-- revoke & grant statements for 3.

REVOKE ALL ON Campaign, Donors, Donations, Workers, CampaignActivity,
                CampaignWorkers, ActivityWorkers, Debates, DebateCandidates
                FROM liyiyu1;

GRANT SELECT (did) ON Debates TO liyiyu1;
GRANT SELECT (candidateEmail) ON Campaign TO liyiyu1;
GRANT SELECT (did, email) ON DebateCandidates TO liyiyu1;


-- 3. Find candidates who are involved in every debate.
-- shuold be in the result: ddd, not in the result: eee, fff

CREATE OR REPLACE VIEW idealD AS -- ideal situation where every candidate is
                                 -- involved in every debate
SELECT DISTINCT * FROM
(SELECT did FROM Debates) d1 -- all unique debate IDs
CROSS JOIN 
(SELECT DISTINCT DebateCandidates.email -- all unique candidate emails
              --(of whom are invloved in at least 1 debate)
FROM Campaign JOIN DebateCandidates ON 
                Campaign.candidateEmail = DebateCandidates.email) d2;

CREATE OR REPLACE VIEW actualD AS -- actual situation of candidate-debate pairs
SELECT did, DebateCandidates.email
FROM Campaign JOIN DebateCandidates ON 
                Campaign.candidateEmail = DebateCandidates.email;

CREATE OR REPLACE VIEW notAllD AS -- emails of candidates who are
                                  -- not involved in every debate
(SELECT did, email FROM idealD)
EXCEPT
(SELECT did, email FROM actualD);

(SELECT email FROM actualD)
EXCEPT
(SELECT email FROM notAllD);