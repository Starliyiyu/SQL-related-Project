-- could not enforce: (1) constraint that the same candidate cannot be at two or
--                        more debates that overlaps in date and time
--                          - because this involves interaction between
--                            2 tables: Debates and DebateCandidates
--                    (2) constraint on assumption (6)
--                          - because this involves interaction between
--                            3 tables: CampaignActivity, ActivityWorkers
--                            and Debates
--                    (3) constraint on assumption (9)
--                          - because this involves interaction between
--                            3 tables: Workers and CampaignActivity and
--                            ActivityWorkers
--                           
-- did not enforce: (1) constraint that the same moderator cannot be at two or
--                      more debates that overlaps in date and time
--                        - it does not involve triggers or assertions
--                          but psql does not support the use of
--                          subquery in check constraint
--
-- extra: (1) check valid format of IDs donation amount and spending limit
--            (aID, cID, dID >= 0, donation amount and spending limit > 0)
--        (2) foreign key constraints to make sure that IDs (aID, cID, dID)
--            exist in the record with delete cascade, note that cID in 
--            Donations has no delete cascade since the record
--            involves money transaction
--        (3) check the input type
--            (donor type, worker type, activity type) exist
--        (4) check valid format of email (____@___.___)

-- assumption: (1) a candidate can only be in 1 campaign, where as
--                 a worker (staff/volunteer) can register to work for
--                 >1 campaigns ("register" = exists in CampaignWorkers);
--             (2) moderator is a worker (as in Workers);
--             (3) a debate/activity has a start time and end time;
--             (4) a worker's schedule has 2 components: the start and end time
--                 of the activity they are scheduled to assist with;
--             (5) a worker can have multiple schedules (responsible for a few
--                 activities) ASSOCIATE WITH a valid activity ID
--                 (recorded in the ActivityWorker table);
--             (6) a worker cannot be at >1 debates/activities within 30 minutes
--                 prior to/after any other debates/activities
--                 they are assigned with;
--             (7) each scheduled campaign activity has a
--                 valid activity ID (aID);
--             (8) a donor can make multiple donations, donations by the same
--                 donor are distinguished by donation time;
--             (9) a worker has to register to work for a campaign to assist in
--                 activities of that campaign;


drop schema if exists election cascade;
create schema election;
set search_path to election;


create domain Email as varchar(320)
        not null
        check (value like '%_@__%.__%'); -- email is of valid format

create table Workers( -- election workers, including all registered
                      -- staff/volunteers for this election
        email Email primary key,
        workerType varchar(20) not null,

        constraint workerType_exist
            check (workerType in ('staff', 'volunteer')));

create table Campaign( --unique campaigns and their spending limits
        cid int primary key,
        cName varchar(100) not null, -- Campaign name
        spendLim int not null,
        candidateEmail Email unique, -- one campaign has only one candidate

        constraint valid_cid_format -- cid has a valid cid format
                check (cid >= 0),

        constraint valid_spending_lim
                check (spendLim >= 0));

create table CampaignWorkers( -- match workers with campaign id
        cid int,
        email Email,

        primary key (cid, email), -- based on assumption (1)

        constraint valid_worker_email -- the email is a valid member email
                foreign key (email) references Workers
                        on delete cascade,
                
        constraint valid_cID 
                foreign key (cid) references Campaign
                        on delete cascade); 

create table CampaignActivity(
        aid int primary key,
        cid int not null,
        start_time timestamp not null,
        end_time timestamp not null,
        activityType varchar(30) not null,
        activitySummary varchar(1000) not null,


        constraint valid_aid_format -- aid has a valid aid format
                check (aid >= 0),

        constraint valid_cID 
                foreign key (cid) references Campaign
                        on delete cascade,

        constraint activity_exist 
                check (activityType in
                ('phone banks', 'door-to-door canvassing')));
                

create table ActivityWorkers( -- match workers with the campaign activities
                              -- they assist in
        aid int,
        email Email,

        primary key (aid, email), -- no need to record repetitive info

        constraint valid_aid -- aid is a valid aid
                foreign key (aid) references CampaignActivity
                        on delete cascade,

        constraint valid_worker_email -- the email is a valid worker email 
                foreign key (email) references Workers
                        on delete cascade);


create table Debates(
        did int primary key,
        start_time timestamp not null,
        end_time timestamp not null,
        email Email, -- moderator email

        constraint valid_did_format -- did has a valid did format
                check (did >= 0),
        
        constraint valid_worker_email -- based on assumption (2)
                foreign key (email) references Workers
                        on delete cascade);


create table DebateCandidates( -- match candidates with the debate
                               -- they participate in
        did int,
        email Email, -- candidate email
        primary key (did, email),-- one candidate only need to be recorded
                                 -- for a debate once
        
        constraint valid_candidate_email
               foreign key (email) references Campaign(candidateEmail)
                        on delete cascade,
                
        constraint valid_dID -- did is a valid debate ID
                foreign key (did) references Debates
                        on delete cascade); 


create table Donors(
        donorEmail Email primary key,
        address varchar(500) not null,
        donorType varchar(12) not null,

        constraint donorType_exist
                check (donorType in ('individual', 'organization')));


create table Donations( -- record of each donation make by a donor
        donorEmail Email,
        amount float not null,
        cid int,
        donateTime timestamp not null,

        primary key (donorEmail, donateTime), -- based on assumption (8)

        constraint valid_amount
                check (amount >= 0),
                
        constraint valid_cID -- cid is a valid Campaign ID
                foreign key (cid) references Campaign);

