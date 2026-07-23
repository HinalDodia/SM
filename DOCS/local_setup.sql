-- ============================================================
-- LOCAL MYSQL SETUP FOR investment DATABASE
-- Run: mysql -u root -p < D:\Desktop\SM\BACKEND\local_setup.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS investment CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE investment;

SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS usermilestones;
DROP TABLE IF EXISTS useractivity;
DROP TABLE IF EXISTS stockhistory;
DROP TABLE IF EXISTS stockdata;
DROP TABLE IF EXISTS transactionhistory;
DROP TABLE IF EXISTS fifolot;
DROP TABLE IF EXISTS watchlist;
DROP TABLE IF EXISTS portfolio;
DROP TABLE IF EXISTS milestones;
DROP TABLE IF EXISTS stock;
DROP TABLE IF EXISTS users;

SET FOREIGN_KEY_CHECKS=1;

-- -------------------------------------------------- users
CREATE TABLE users (
  userid        INT            NOT NULL AUTO_INCREMENT,
  name          VARCHAR(50)    NOT NULL,
  email         VARCHAR(100)   NOT NULL,
  password_hash VARCHAR(1024)  DEFAULT NULL,
  otp_code      VARCHAR(10)    DEFAULT NULL,
  otp_ts        DATETIME       DEFAULT NULL,
  money         DECIMAL(12,2)  DEFAULT '10000.00',
  profitorloss  DECIMAL(12,2)  DEFAULT '0.00',
  profitpercent FLOAT          DEFAULT '0',
  losspercent   FLOAT          DEFAULT '0',
  last_login    DATETIME       DEFAULT NULL,
  progress      INT            DEFAULT '0',
  level         VARCHAR(20)    DEFAULT 'Beginner',
  PRIMARY KEY (userid),
  UNIQUE KEY email (email)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET sql_mode = '';

INSERT INTO users
  (userid, name, email, money, profitorloss, profitpercent, losspercent, last_login, progress, level, password_hash, otp_code, otp_ts)
VALUES
(1,'alice','alice@gmail.com',10000.00,0.01,0,0,NULL,0,'Beginner','scrypt:32768:8:1$TbAJPKMhAv1NOfpw$42275916c00af9f22cd957c5738858e52706e4770e7ba12c5e196af99b95895cbc33db8d29b0a476efa8a0e876fe2643bee0ed703ca3a52211514495b0ce8914',NULL,NULL),
(2,'hinal dodia','hinaldodia67678@gmail.com',10000.00,0.00,0,0,'2026-01-02 08:16:04',0,'Beginner','scrypt:32768:8:1$67HgRRyqhaNSKTwo$8ad7e209d863affa3910dc0511ad556c770ee627108923956e6d082d4c11852b469300f6b5eb28c8bdc414d4d00f1957e84c31dbfba6cf343809615dbdd2b276',NULL,NULL),
(3,'ashwin dodia','ashwindodia1@gmail.com',10000.00,0.00,0,0,'2025-12-29 09:24:52',0,'Beginner','scrypt:32768:8:1$E2BmO8KhEFZLZdA1$ea825b96ca4df0e37d686a0925e1cd2d5b3913bdd966b5b365b01087064ea48a25575bd96fed7365d5a4eb5cdee10b5347aa6390220e791a4c1510ee3175e832',NULL,NULL),
(4,'Rohan Dodia','rohandodia1@gmail.com',10000.00,0.00,0,0,'2025-12-29 09:22:56',0,'Beginner','scrypt:32768:8:1$zhaSecTFttnoGsL2$acf7b981d3c84b1a040c87e3b1474e7f1c2f28ecad015ed82d75f777172626bbf1b75363e40d639ab89f092e6bb700938c861f1792ccecd5f7067169c6a34f97',NULL,NULL),
(5,'hinal dodia','hinaldodia17@gmail.com',10000.00,0.00,0,0,'2026-01-06 14:43:00',0,'Beginner','scrypt:32768:8:1$Arbjvc7gm7Jwq8R7$a8ab65c6fd2139a5c7fd773c5fc511fcc2f8d74e6e6abcf162f9c57065400abf57f33525a79a0f48f8b8548deb20264123fcff1f56b235ef9d8f581b296aba6e',NULL,NULL),
(7,'Rohan Dodia','rohandodia21@gmail.com',10000.00,0.00,0,0,'2026-05-05 11:25:07',0,'Beginner','scrypt:32768:8:1$Pml4z79BbJxtGAjy$01ace4b8bce40d2926d396fa2c9edfb51961dc2b4ebe03c871778514745c2fe1b283c9dba3016bb278cb0741bd72752982c3cb00ab91722f308fdee68990b0b4',NULL,NULL),
(9,'Deep Rathod','deeprathod216@gmail.com',1333.10,0.00,0,0,'2026-05-31 10:08:54',0,'Beginner','scrypt:32768:8:1$A1KHVO4fKMrwRiRG$b9f75c2a8b820b30a68302f272a90558ef72788c678d06e6974dd596d6d1bdd516008194ff1011304da291b98f78bf19f28e110342cb88477362c703bc6899f8',NULL,NULL);

-- -------------------------------------------------- stock
CREATE TABLE stock (
  stock_id     INT          NOT NULL AUTO_INCREMENT,
  stock_symbol VARCHAR(10)  NOT NULL,
  stock_name   VARCHAR(100) DEFAULT NULL,
  PRIMARY KEY (stock_id),
  UNIQUE KEY stock_symbol (stock_symbol)
) ENGINE=InnoDB AUTO_INCREMENT=4139 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO stock VALUES
(4099,'RELIANCE','Reliance Industries Ltd'),(4100,'TCS','Tata Consultancy Services Ltd'),
(4101,'INFY','Infosys Ltd'),(4102,'HDFCBANK','HDFC Bank Ltd'),
(4103,'ICICIBANK','ICICI Bank Ltd'),(4104,'SBIN','State Bank of India'),
(4105,'AXISBANK','Axis Bank Ltd'),(4106,'KOTAKBANK','Kotak Mahindra Bank Ltd'),
(4107,'BAJFINANCE','Bajaj Finance Ltd'),(4108,'BAJAJFINSV','Bajaj Finserv Ltd'),
(4109,'LT','Larsen & Toubro Ltd'),(4110,'ITC','ITC Ltd'),
(4111,'HINDUNILVR','Hindustan Unilever Ltd'),(4112,'NESTLEIND','Nestle India Ltd'),
(4113,'BRITANNIA','Britannia Industries Ltd'),(4114,'TITAN','Titan Company Ltd'),
(4115,'MARUTI','Maruti Suzuki India Ltd'),(4116,'EICHERMOT','Eicher Motors Ltd'),
(4117,'HEROMOTOCO','Hero MotoCorp Ltd'),(4118,'TATASTEEL','Tata Steel Ltd'),
(4119,'JSWSTEEL','JSW Steel Ltd'),(4120,'ULTRACEMCO','UltraTech Cement Ltd'),
(4121,'POWERGRID','Power Grid Corporation of India Ltd'),(4122,'NTPC','NTPC Ltd'),
(4123,'ONGC','Oil & Natural Gas Corporation Ltd'),(4124,'SUNPHARMA','Sun Pharmaceutical Industries Ltd'),
(4125,'DRREDDY',"Dr Reddy's Laboratories Ltd"),(4126,'CIPLA','Cipla Ltd'),
(4127,'DIVISLAB',"Divi's Laboratories Ltd"),(4128,'APOLLOHOSP','Apollo Hospitals Enterprise Ltd'),
(4129,'HCLTECH','HCL Technologies Ltd'),(4130,'TECHM','Tech Mahindra Ltd'),
(4131,'WIPRO','Wipro Ltd'),(4132,'ADANIENT','Adani Enterprises Ltd'),
(4133,'ADANIPORTS','Adani Ports and SEZ Ltd'),(4134,'COALINDIA','Coal India Ltd'),
(4135,'INDUSINDBK','IndusInd Bank Ltd'),(4136,'PIDILITIND','Pidilite Industries Ltd'),
(4137,'ASIANPAINT','Asian Paints Ltd'),(4138,'GRASIM','Grasim Industries Ltd');

-- -------------------------------------------------- milestones
CREATE TABLE milestones (
  milestone_id    INT          NOT NULL AUTO_INCREMENT,
  name            VARCHAR(50)  DEFAULT NULL,
  description     VARCHAR(255) DEFAULT NULL,
  type            VARCHAR(20)  DEFAULT NULL,
  threshold_value FLOAT        DEFAULT NULL,
  PRIMARY KEY (milestone_id)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO milestones VALUES
(1,'Beginner Investor','Own at least 1 stock in your portfolio','portfolio',1),
(2,'Intermediate Investor','Own at least 6 stocks in your portfolio','portfolio',6),
(3,'Advanced Investor','Own at least 11 stocks in your portfolio','portfolio',11),
(4,'Profit Novice','Achieve at least 5% profit on investments','profit',5),
(5,'Profit Achiever','Achieve at least 20% profit on investments','profit',20),
(6,'Profit Expert','Achieve at least 51% profit on investments','profit',51),
(7,'3-Day Streak','Log in or trade for 3 consecutive days','consistency',3),
(8,'7-Day Streak','Log in or trade for 7 consecutive days','consistency',7),
(9,'30-Day Streak','Log in or trade for 30 consecutive days','consistency',30);

-- -------------------------------------------------- portfolio
CREATE TABLE portfolio (
  portfolioid    INT            NOT NULL AUTO_INCREMENT,
  userid         INT            DEFAULT NULL,
  stock_id       INT            NOT NULL,
  stockname      VARCHAR(100)   DEFAULT NULL,
  companyname    VARCHAR(100)   DEFAULT NULL,
  totalquantity  INT            DEFAULT '0',
  averagebuyprice DECIMAL(12,2) DEFAULT '0.00',
  totalinvested  DECIMAL(12,2)  DEFAULT '0.00',
  sector         VARCHAR(100)   DEFAULT NULL,
  PRIMARY KEY (portfolioid),
  KEY portfolio_ibfk_1 (userid),
  CONSTRAINT portfolio_ibfk_1 FOREIGN KEY (userid) REFERENCES users (userid) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=59 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO portfolio VALUES
(49,9,4121,'POWERGRID','Power Grid Corporation of India Ltd',0,0.00,0.00,'Utilities'),
(50,9,4105,'AXISBANK','Axis Bank Ltd',0,0.00,0.00,'Financial Services'),
(51,9,4099,'RELIANCE','Reliance Industries Ltd',0,0.00,0.00,'Energy'),
(52,9,4128,'APOLLOHOSP','Apollo Hospitals Enterprise Ltd',0,0.00,0.00,'Healthcare'),
(53,9,4100,'TCS','Tata Consultancy Services Ltd',2,2335.23,4670.46,'Technology'),
(54,9,4101,'INFY','Infosys Ltd',2,1319.20,2638.40,'Technology'),
(55,9,4102,'HDFCBANK','HDFC Bank Ltd',0,0.00,0.00,'Financial Services'),
(56,9,4134,'COALINDIA','Coal India Ltd',0,0.00,0.00,'Energy'),
(57,9,4124,'SUNPHARMA','Sun Pharmaceutical Industries Ltd',0,0.00,0.00,'Healthcare'),
(58,9,4106,'KOTAKBANK','Kotak Mahindra Bank Ltd',3,377.10,1131.30,'Financial Services');

-- -------------------------------------------------- watchlist
CREATE TABLE watchlist (
  watchlist_id INT NOT NULL AUTO_INCREMENT,
  user_id      INT NOT NULL,
  stock_id     INT NOT NULL,
  PRIMARY KEY (watchlist_id),
  KEY stock_id (stock_id),
  KEY watchlist_ibfk_1 (user_id),
  CONSTRAINT watchlist_ibfk_1 FOREIGN KEY (user_id) REFERENCES users (userid) ON DELETE CASCADE,
  CONSTRAINT watchlist_ibfk_2 FOREIGN KEY (stock_id) REFERENCES stock (stock_id)
) ENGINE=InnoDB AUTO_INCREMENT=122 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO watchlist VALUES (116,9,4127),(118,9,4103),(121,9,4128);

-- -------------------------------------------------- transactionhistory
CREATE TABLE transactionhistory (
  transactionid   INT            NOT NULL AUTO_INCREMENT,
  userid          INT            NOT NULL,
  portfolioid     INT            NOT NULL,
  companyname     VARCHAR(100)   NOT NULL,
  stockname       VARCHAR(100)   NOT NULL,
  quantity        INT            NOT NULL,
  price           DECIMAL(12,2)  NOT NULL,
  transactiontype VARCHAR(10)    NOT NULL,
  timestamp       DATETIME       DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (transactionid),
  KEY portfolioid (portfolioid),
  KEY transactionhistory_ibfk_1 (userid),
  CONSTRAINT transactionhistory_ibfk_1 FOREIGN KEY (userid) REFERENCES users (userid) ON DELETE CASCADE,
  CONSTRAINT transactionhistory_ibfk_2 FOREIGN KEY (portfolioid) REFERENCES portfolio (portfolioid)
) ENGINE=InnoDB AUTO_INCREMENT=237 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO transactionhistory VALUES
(204,9,49,'Power Grid Corporation of India Ltd','POWERGRID',3,298.05,'BUY','2026-03-16 07:33:35'),
(205,9,50,'Axis Bank Ltd','AXISBANK',2,1199.80,'BUY','2026-03-16 07:34:11'),
(206,9,51,'Reliance Industries Ltd','RELIANCE',3,1376.40,'BUY','2026-03-16 07:35:03'),
(207,9,51,'Reliance Industries Ltd','RELIANCE',2,1376.40,'sell','2026-03-16 07:35:29'),
(208,9,50,'Axis Bank Ltd','AXISBANK',2,1199.80,'sell','2026-03-16 07:35:41'),
(209,9,49,'Power Grid Corporation of India Ltd','POWERGRID',3,298.05,'sell','2026-03-16 07:36:10'),
(210,9,51,'Reliance Industries Ltd','RELIANCE',1,1376.40,'sell','2026-03-16 07:36:16'),
(211,9,50,'Axis Bank Ltd','AXISBANK',2,1205.20,'BUY','2026-03-29 11:17:00'),
(212,9,52,'Apollo Hospitals Enterprise Ltd','APOLLOHOSP',1,7549.00,'BUY','2026-03-29 11:17:07'),
(213,9,50,'Axis Bank Ltd','AXISBANK',1,1205.20,'sell','2026-03-29 11:17:21'),
(214,9,52,'Apollo Hospitals Enterprise Ltd','APOLLOHOSP',1,7549.00,'sell','2026-03-29 11:18:31'),
(215,9,50,'Axis Bank Ltd','AXISBANK',1,1205.20,'sell','2026-04-04 04:50:33'),
(216,9,50,'Axis Bank Ltd','AXISBANK',2,1197.90,'BUY','2026-04-04 11:51:35'),
(217,9,53,'Tata Consultancy Services Ltd','TCS',1,2576.90,'BUY','2026-04-16 11:45:30'),
(218,9,54,'Infosys Ltd','INFY',2,1319.20,'BUY','2026-04-16 11:45:39'),
(219,9,50,'Axis Bank Ltd','AXISBANK',2,1197.90,'sell','2026-04-16 04:45:53'),
(220,9,53,'Tata Consultancy Services Ltd','TCS',1,2394.40,'buy','2026-05-09 17:00:30'),
(221,9,53,'Tata Consultancy Services Ltd','TCS',1,2394.40,'sell','2026-05-09 17:01:37'),
(222,9,53,'Tata Consultancy Services Ltd','TCS',1,2394.40,'buy','2026-05-09 17:02:42'),
(223,9,53,'Tata Consultancy Services Ltd','TCS',1,2394.40,'sell','2026-05-09 17:03:05'),
(224,9,53,'Tata Consultancy Services Ltd','TCS',1,2300.30,'buy','2026-05-12 20:23:03'),
(225,9,53,'Tata Consultancy Services Ltd','TCS',1,2300.30,'sell','2026-05-12 20:23:18'),
(226,9,53,'Tata Consultancy Services Ltd','TCS',1,2300.30,'BUY','2026-05-12 15:57:03'),
(227,9,51,'Reliance Industries Ltd','RELIANCE',1,1364.00,'BUY','2026-05-12 15:57:53'),
(228,9,51,'Reliance Industries Ltd','RELIANCE',1,1364.00,'sell','2026-05-12 21:28:58'),
(229,9,55,'HDFC Bank Ltd','HDFCBANK',1,750.45,'BUY','2026-05-12 18:18:38'),
(230,9,56,'Coal India Ltd','COALINDIA',1,463.05,'BUY','2026-05-12 18:25:11'),
(231,9,55,'HDFC Bank Ltd','HDFCBANK',1,750.45,'sell','2026-05-12 23:59:27'),
(232,9,56,'Coal India Ltd','COALINDIA',1,463.05,'sell','2026-05-12 23:59:40'),
(233,9,57,'Sun Pharmaceutical Industries Ltd','SUNPHARMA',1,1845.70,'BUY','2026-05-12 18:30:25'),
(234,9,58,'Kotak Mahindra Bank Ltd','KOTAKBANK',1,376.00,'BUY','2026-05-12 18:34:13'),
(235,9,57,'Sun Pharmaceutical Industries Ltd','SUNPHARMA',1,1825.70,'sell','2026-05-13 15:12:42'),
(236,9,58,'Kotak Mahindra Bank Ltd','KOTAKBANK',2,377.65,'BUY','2026-05-13 11:16:21');

-- -------------------------------------------------- fifolot
CREATE TABLE fifolot (
  lotid             INT            NOT NULL AUTO_INCREMENT,
  userid            INT            NOT NULL,
  portfolioid       INT            NOT NULL,
  companyname       VARCHAR(100)   NOT NULL,
  quantityremaining INT            NOT NULL,
  pricepershare     DECIMAL(12,2)  NOT NULL,
  buydate           DATETIME       DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (lotid),
  KEY portfolioid (portfolioid),
  KEY fifolot_ibfk_1 (userid),
  CONSTRAINT fifolot_ibfk_1 FOREIGN KEY (userid) REFERENCES users (userid) ON DELETE CASCADE,
  CONSTRAINT fifolot_ibfk_2 FOREIGN KEY (portfolioid) REFERENCES portfolio (portfolioid)
) ENGINE=InnoDB AUTO_INCREMENT=106 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO fifolot VALUES
(91,9,49,'Power Grid Corporation of India Ltd',3,298.05,'2026-03-16 07:33:35'),
(92,9,50,'Axis Bank Ltd',2,1199.80,'2026-03-16 07:34:11'),
(93,9,51,'Reliance Industries Ltd',3,1376.40,'2026-03-16 07:35:03'),
(94,9,50,'Axis Bank Ltd',2,1205.20,'2026-03-29 11:17:00'),
(95,9,52,'Apollo Hospitals Enterprise Ltd',1,7549.00,'2026-03-29 11:17:07'),
(96,9,50,'Axis Bank Ltd',2,1197.90,'2026-04-04 11:51:35'),
(97,9,53,'Tata Consultancy Services Ltd',1,2576.90,'2026-04-16 11:45:30'),
(98,9,54,'Infosys Ltd',2,1319.20,'2026-04-16 11:45:39'),
(99,9,53,'Tata Consultancy Services Ltd',1,2300.30,'2026-05-12 15:57:03'),
(100,9,51,'Reliance Industries Ltd',1,1364.00,'2026-05-12 15:57:53'),
(101,9,55,'HDFC Bank Ltd',1,750.45,'2026-05-12 18:18:38'),
(102,9,56,'Coal India Ltd',1,463.05,'2026-05-12 18:25:11'),
(103,9,57,'Sun Pharmaceutical Industries Ltd',1,1845.70,'2026-05-12 18:30:25'),
(104,9,58,'Kotak Mahindra Bank Ltd',1,376.00,'2026-05-12 18:34:13'),
(105,9,58,'Kotak Mahindra Bank Ltd',2,377.65,'2026-05-13 11:16:21');

-- -------------------------------------------------- stockhistory
CREATE TABLE stockhistory (
  id          INT         NOT NULL AUTO_INCREMENT,
  userid      INT         NOT NULL,
  stock_name  VARCHAR(50) NOT NULL,
  dates       DATE        NOT NULL,
  close_price FLOAT       NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY unique_user_stock_date (userid, stock_name, dates),
  CONSTRAINT stockhistory_ibfk_1 FOREIGN KEY (userid) REFERENCES users (userid) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=539 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO stockhistory VALUES
(513,9,'INFY','2025-11-17',17.7),(514,9,'INFY','2025-11-24',17.48),
(515,9,'INFY','2025-12-01',18.07),(516,9,'INFY','2025-12-08',17.78),
(517,9,'INFY','2025-12-15',20.22),(518,9,'INFY','2025-12-22',18.79),
(519,9,'INFY','2025-12-29',18.15),(520,9,'INFY','2026-01-05',17.83),
(521,9,'INFY','2026-01-12',18.63),(522,9,'INFY','2026-01-19',18.24),
(523,9,'INFY','2026-01-26',17.58),(524,9,'INFY','2026-02-02',16.84),
(525,9,'INFY','2026-02-09',14.72),(526,9,'INFY','2026-02-16',14.65),
(527,9,'INFY','2026-02-23',14.44),(528,9,'INFY','2026-03-02',14.44),
(529,9,'INFY','2026-03-09',13.27),(530,9,'INFY','2026-03-16',13.12),
(531,9,'INFY','2026-03-23',12.83),(532,9,'INFY','2026-03-30',13.74),
(533,9,'INFY','2026-04-06',13.29),(534,9,'INFY','2026-04-13',14.46),
(535,9,'INFY','2026-04-20',12.86),(536,9,'INFY','2026-04-27',12.48),
(537,9,'INFY','2026-05-04',12.83),(538,9,'INFY','2026-05-11',12.05);

-- -------------------------------------------------- stockdata
CREATE TABLE stockdata (
  id       INT         NOT NULL AUTO_INCREMENT,
  symbol   VARCHAR(30) DEFAULT NULL,
  date     DATE        DEFAULT NULL,
  open     FLOAT       DEFAULT NULL,
  high     FLOAT       DEFAULT NULL,
  low      FLOAT       DEFAULT NULL,
  close    FLOAT       DEFAULT NULL,
  adj_close FLOAT      DEFAULT NULL,
  volume   BIGINT      DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY symbol (symbol, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------- useractivity
CREATE TABLE useractivity (
  activity_id    INT         NOT NULL AUTO_INCREMENT,
  userid         INT         NOT NULL,
  activity_type  VARCHAR(50) NOT NULL,
  activity_value FLOAT       DEFAULT '0',
  activity_date  DATETIME    DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (activity_id),
  KEY useractivity_ibfk_1 (userid),
  CONSTRAINT useractivity_ibfk_1 FOREIGN KEY (userid) REFERENCES users (userid) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=44 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO useractivity VALUES
(1,1,'sell',80.24,'2025-09-11 03:10:18'),(4,1,'sell',3124.2,'2025-09-11 03:21:16'),
(5,1,'buy',3124.2,'2025-09-11 03:30:48'),(6,1,'buy',3124.2,'2025-09-11 03:30:50'),
(7,1,'sell',160.48,'2025-09-11 03:42:13'),(8,1,'sell',6248.4,'2025-09-11 03:42:19'),
(9,1,'sell',1004.2,'2025-09-11 03:43:21'),(10,1,'sell',80.24,'2025-09-11 03:43:26'),
(24,1,'buy',3124.2,'2025-09-11 11:22:50'),(25,1,'buy',3124.2,'2025-09-11 11:23:18'),
(26,1,'sell',3124.2,'2025-09-11 11:50:29'),(29,1,'buy',3133.4,'2025-09-12 10:57:28'),
(30,1,'sell',1616.6,'2025-09-13 04:42:40'),(31,1,'sell',1806.1,'2025-10-12 10:20:14'),
(43,1,'sell',1036.5,'2025-10-17 04:12:26');

-- -------------------------------------------------- usermilestones
CREATE TABLE usermilestones (
  usermilestone_id INT      NOT NULL AUTO_INCREMENT,
  userid           INT      DEFAULT NULL,
  milestone_id     INT      DEFAULT NULL,
  achieved_on      DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (usermilestone_id),
  KEY milestone_id (milestone_id),
  KEY usermilestones_ibfk_1 (userid),
  CONSTRAINT usermilestones_ibfk_1 FOREIGN KEY (userid) REFERENCES users (userid) ON DELETE CASCADE,
  CONSTRAINT usermilestones_ibfk_2 FOREIGN KEY (milestone_id) REFERENCES milestones (milestone_id)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO usermilestones VALUES
(1,1,1,'2025-09-11 05:06:39'),
(2,1,2,'2025-09-11 05:06:39'),
(3,1,3,'2025-09-11 07:05:08');

-- Done!
SELECT 'Migration complete!' AS status;
