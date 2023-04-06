-- some campaigns
INSERT INTO Campaign VALUES
(1, 'Camp. A', 500000, 'ddd@gmail.com'), 
(2, 'Camp. B', 500000, 'eee@gmail.com'), 
(4, 'Camp. D', 500000, 'fff@gmail.com'), 
(3, 'Camp. C', 500000, 'xxx@gmail.com');

-- some donors
INSERT INTO Donors VALUES
('angelaz@gmail.com', 'address1', 'individual'), 
('mandym@gmail.com', 'address2', 'individual'), 
('starl@gmail.com', 'address3', 'organization'), 
('jaes@gmail.com', 'address4', 'organization');

-- some donations
INSERT INTO Donations VALUES
('angelaz@gmail.com', 5000, 1, '2023-05-03 08:15:06'), 
('mandym@gmail.com', 1000, 1, '2023-05-08 08:15:06'), 
('starl@gmail.com', 100000, 3, '2023-05-07 08:15:06'), 
('jaes@gmail.com', 50000, 3, '2023-05-06 08:15:06'),
('starl@gmail.com', 100000, 1, '2023-05-05 08:15:06'), 
('jaes@gmail.com', 500, 3, '2023-05-04 08:15:06');

-- some members
INSERT INTO Workers VALUES
('aaa@gmail.com', 'volunteer'), 
('bbb@gmail.com', 'volunteer'), 
('ccc@gmail.com', 'volunteer');

-- some activities
INSERT INTO CampaignActivity VALUES
(111, 1, '2023-09-03 08:15:06', '2023-09-03 13:15:06',
 'phone banks', 'activity details'), 
(222, 2, '2023-09-04 08:15:06', '2023-09-04 13:15:06',
 'phone banks', 'activity details'), 
(333, 3, '2023-09-05 08:15:06', '2023-09-05 13:15:06',
 'phone banks', 'activity details'), 
(444, 4, '2023-09-06 08:15:06', '2023-09-06 13:15:06',
 'phone banks', 'activity details');

-- some member x campaign
INSERT INTO CampaignWorkers VALUES
(1, 'aaa@gmail.com'), 
(2, 'aaa@gmail.com'),
(3, 'aaa@gmail.com'),
(4, 'aaa@gmail.com'),
(1, 'bbb@gmail.com'), 
(2, 'bbb@gmail.com'), 
(3, 'bbb@gmail.com'), 
(4, 'bbb@gmail.com'), 
(3, 'ccc@gmail.com');

-- some workers x activities
INSERT INTO ActivityWorkers VALUES
(111, 'aaa@gmail.com'), 
(222, 'aaa@gmail.com'),
(333, 'aaa@gmail.com'),
(444, 'aaa@gmail.com'),
(111, 'bbb@gmail.com'), 
(222, 'bbb@gmail.com'), 
(333, 'bbb@gmail.com'), 
(444, 'bbb@gmail.com'), 
(333, 'ccc@gmail.com'), 
(444, 'ccc@gmail.com'),
(111, 'ccc@gmail.com');

-- some debates
INSERT INTO Debates VALUES
(1, '2023-06-03 08:15:06', '2023-06-03 13:15:06', 'ccc@gmail.com'),
(2, '2023-06-04 08:15:06', '2023-06-04 13:15:06', 'bbb@gmail.com'),
(3, '2023-06-05 08:15:06', '2023-06-05 13:15:06', 'aaa@gmail.com');

-- some debate x candidate
INSERT INTO DebateCandidates VALUES 
(1, 'ddd@gmail.com'),
(2, 'ddd@gmail.com'),
(1, 'eee@gmail.com'),
(3, 'ddd@gmail.com'),
(2, 'eee@gmail.com'),
(2, 'fff@gmail.com'),
(1, 'fff@gmail.com');