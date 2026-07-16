-- MySQL dump 10.13  Distrib 8.0.46, for Win64 (x86_64)
--
-- Host: investment-db.c3k8wc4ci776.ap-south-1.rds.amazonaws.com    Database: investment
-- ------------------------------------------------------
-- Server version	8.0.44

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `investment`
--

USE `investment`;

--
-- Table structure for table `fifolot`
--

DROP TABLE IF EXISTS `fifolot`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `fifolot` (
  `lotid` int NOT NULL AUTO_INCREMENT,
  `userid` int NOT NULL,
  `portfolioid` int NOT NULL,
  `companyname` varchar(100) NOT NULL,
  `quantityremaining` int NOT NULL,
  `pricepershare` decimal(12,2) NOT NULL,
  `buydate` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`lotid`),
  KEY `portfolioid` (`portfolioid`),
  KEY `fifolot_ibfk_1` (`userid`),
  CONSTRAINT `fifolot_ibfk_1` FOREIGN KEY (`userid`) REFERENCES `users` (`userid`) ON DELETE CASCADE,
  CONSTRAINT `fifolot_ibfk_2` FOREIGN KEY (`portfolioid`) REFERENCES `portfolio` (`portfolioid`)
) ENGINE=InnoDB AUTO_INCREMENT=106 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `fifolot`
--

LOCK TABLES `fifolot` WRITE;
/*!40000 ALTER TABLE `fifolot` DISABLE KEYS */;
INSERT INTO `fifolot` VALUES (91,9,49,'Power Grid Corporation of India Ltd\r',3,298.05,'2026-03-16 07:33:35'),(92,9,50,'Axis Bank Ltd\r',2,1199.80,'2026-03-16 07:34:11'),(93,9,51,'Reliance Industries Ltd\r',3,1376.40,'2026-03-16 07:35:03'),(94,9,50,'Axis Bank Ltd\r',2,1205.20,'2026-03-29 11:17:00'),(95,9,52,'Apollo Hospitals Enterprise Ltd\r',1,7549.00,'2026-03-29 11:17:07'),(96,9,50,'Axis Bank Ltd\r',2,1197.90,'2026-04-04 11:51:35'),(97,9,53,'Tata Consultancy Services Ltd\r',1,2576.90,'2026-04-16 11:45:30'),(98,9,54,'Infosys Ltd\r',2,1319.20,'2026-04-16 11:45:39'),(99,9,53,'Tata Consultancy Services Ltd\r',1,2300.30,'2026-05-12 15:57:03'),(100,9,51,'Reliance Industries Ltd\r',1,1364.00,'2026-05-12 15:57:53'),(101,9,55,'HDFC Bank Ltd\r',1,750.45,'2026-05-12 18:18:38'),(102,9,56,'Coal India Ltd\r',1,463.05,'2026-05-12 18:25:11'),(103,9,57,'Sun Pharmaceutical Industries Ltd\r',1,1845.70,'2026-05-12 18:30:25'),(104,9,58,'Kotak Mahindra Bank Ltd\r',1,376.00,'2026-05-12 18:34:13'),(105,9,58,'Kotak Mahindra Bank Ltd\r',2,377.65,'2026-05-13 11:16:21');
/*!40000 ALTER TABLE `fifolot` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `milestones`
--

DROP TABLE IF EXISTS `milestones`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `milestones` (
  `milestone_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `type` varchar(20) DEFAULT NULL,
  `threshold_value` float DEFAULT NULL,
  PRIMARY KEY (`milestone_id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `milestones`
--

LOCK TABLES `milestones` WRITE;
/*!40000 ALTER TABLE `milestones` DISABLE KEYS */;
INSERT INTO `milestones` VALUES (1,'Beginner Investor','Own at least 1 stock in your portfolio','portfolio',1),(2,'Intermediate Investor','Own at least 6 stocks in your portfolio','portfolio',6),(3,'Advanced Investor','Own at least 11 stocks in your portfolio','portfolio',11),(4,'Profit Novice','Achieve at least 5% profit on investments','profit',5),(5,'Profit Achiever','Achieve at least 20% profit on investments','profit',20),(6,'Profit Expert','Achieve at least 51% profit on investments','profit',51),(7,'3-Day Streak','Log in or trade for 3 consecutive days','consistency',3),(8,'7-Day Streak','Log in or trade for 7 consecutive days','consistency',7),(9,'30-Day Streak','Log in or trade for 30 consecutive days','consistency',30);
/*!40000 ALTER TABLE `milestones` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `portfolio`
--

DROP TABLE IF EXISTS `portfolio`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `portfolio` (
  `portfolioid` int NOT NULL AUTO_INCREMENT,
  `userid` int DEFAULT NULL,
  `stock_id` int NOT NULL,
  `stockname` varchar(100) DEFAULT NULL,
  `companyname` varchar(100) DEFAULT NULL,
  `totalquantity` int DEFAULT '0',
  `averagebuyprice` decimal(12,2) DEFAULT '0.00',
  `totalinvested` decimal(12,2) DEFAULT '0.00',
  `sector` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`portfolioid`),
  KEY `portfolio_ibfk_1` (`userid`),
  CONSTRAINT `portfolio_ibfk_1` FOREIGN KEY (`userid`) REFERENCES `users` (`userid`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=59 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `portfolio`
--

LOCK TABLES `portfolio` WRITE;
/*!40000 ALTER TABLE `portfolio` DISABLE KEYS */;
INSERT INTO `portfolio` VALUES (49,9,4121,'POWERGRID','Power Grid Corporation of India Ltd\r',0,0.00,0.00,'Utilities'),(50,9,4105,'AXISBANK','Axis Bank Ltd\r',0,0.00,0.00,'Financial Services'),(51,9,4099,'RELIANCE','Reliance Industries Ltd\r',0,0.00,0.00,'Energy'),(52,9,4128,'APOLLOHOSP','Apollo Hospitals Enterprise Ltd\r',0,0.00,0.00,'Healthcare'),(53,9,4100,'TCS','Tata Consultancy Services Ltd\r',2,2335.23,4670.46,'Technology'),(54,9,4101,'INFY','Infosys Ltd\r',2,1319.20,2638.40,'Technology'),(55,9,4102,'HDFCBANK','HDFC Bank Ltd\r',0,0.00,0.00,'Financial Services'),(56,9,4134,'COALINDIA','Coal India Ltd\r',0,0.00,0.00,'Energy'),(57,9,4124,'SUNPHARMA','Sun Pharmaceutical Industries Ltd\r',0,0.00,0.00,'Healthcare'),(58,9,4106,'KOTAKBANK','Kotak Mahindra Bank Ltd\r',3,377.10,1131.30,'Financial Services');
/*!40000 ALTER TABLE `portfolio` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `stock`
--

DROP TABLE IF EXISTS `stock`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stock` (
  `stock_id` int NOT NULL AUTO_INCREMENT,
  `stock_symbol` varchar(10) NOT NULL,
  `stock_name` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`stock_id`),
  UNIQUE KEY `stock_symbol` (`stock_symbol`)
) ENGINE=InnoDB AUTO_INCREMENT=4139 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `stock`
--

LOCK TABLES `stock` WRITE;
/*!40000 ALTER TABLE `stock` DISABLE KEYS */;
INSERT INTO `stock` VALUES (4099,'RELIANCE','Reliance Industries Ltd\r'),(4100,'TCS','Tata Consultancy Services Ltd\r'),(4101,'INFY','Infosys Ltd\r'),(4102,'HDFCBANK','HDFC Bank Ltd\r'),(4103,'ICICIBANK','ICICI Bank Ltd\r'),(4104,'SBIN','State Bank of India\r'),(4105,'AXISBANK','Axis Bank Ltd\r'),(4106,'KOTAKBANK','Kotak Mahindra Bank Ltd\r'),(4107,'BAJFINANCE','Bajaj Finance Ltd\r'),(4108,'BAJAJFINSV','Bajaj Finserv Ltd\r'),(4109,'LT','Larsen & Toubro Ltd\r'),(4110,'ITC','ITC Ltd\r'),(4111,'HINDUNILVR','Hindustan Unilever Ltd\r'),(4112,'NESTLEIND','Nestle India Ltd\r'),(4113,'BRITANNIA','Britannia Industries Ltd\r'),(4114,'TITAN','Titan Company Ltd\r'),(4115,'MARUTI','Maruti Suzuki India Ltd\r'),(4116,'EICHERMOT','Eicher Motors Ltd\r'),(4117,'HEROMOTOCO','Hero MotoCorp Ltd\r'),(4118,'TATASTEEL','Tata Steel Ltd\r'),(4119,'JSWSTEEL','JSW Steel Ltd\r'),(4120,'ULTRACEMCO','UltraTech Cement Ltd\r'),(4121,'POWERGRID','Power Grid Corporation of India Ltd\r'),(4122,'NTPC','NTPC Ltd\r'),(4123,'ONGC','Oil & Natural Gas Corporation Ltd\r'),(4124,'SUNPHARMA','Sun Pharmaceutical Industries Ltd\r'),(4125,'DRREDDY','Dr Reddy\'s Laboratories Ltd\r'),(4126,'CIPLA','Cipla Ltd\r'),(4127,'DIVISLAB','Divi\'s Laboratories Ltd\r'),(4128,'APOLLOHOSP','Apollo Hospitals Enterprise Ltd\r'),(4129,'HCLTECH','HCL Technologies Ltd\r'),(4130,'TECHM','Tech Mahindra Ltd\r'),(4131,'WIPRO','Wipro Ltd\r'),(4132,'ADANIENT','Adani Enterprises Ltd\r'),(4133,'ADANIPORTS','Adani Ports and SEZ Ltd\r'),(4134,'COALINDIA','Coal India Ltd\r'),(4135,'INDUSINDBK','IndusInd Bank Ltd\r'),(4136,'PIDILITIND','Pidilite Industries Ltd\r'),(4137,'ASIANPAINT','Asian Paints Ltd\r'),(4138,'GRASIM','Grasim Industries Ltd\r');
/*!40000 ALTER TABLE `stock` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `stockdata`
--

DROP TABLE IF EXISTS `stockdata`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stockdata` (
  `id` int NOT NULL AUTO_INCREMENT,
  `symbol` varchar(30) DEFAULT NULL,
  `date` date DEFAULT NULL,
  `open` float DEFAULT NULL,
  `high` float DEFAULT NULL,
  `low` float DEFAULT NULL,
  `close` float DEFAULT NULL,
  `adj_close` float DEFAULT NULL,
  `volume` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `symbol` (`symbol`,`date`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `stockdata`
--

LOCK TABLES `stockdata` WRITE;
/*!40000 ALTER TABLE `stockdata` DISABLE KEYS */;
/*!40000 ALTER TABLE `stockdata` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `stockhistory`
--

DROP TABLE IF EXISTS `stockhistory`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stockhistory` (
  `id` int NOT NULL AUTO_INCREMENT,
  `userid` int NOT NULL,
  `stock_name` varchar(50) NOT NULL,
  `dates` date NOT NULL,
  `close_price` float NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_stock_date` (`userid`,`stock_name`,`dates`),
  CONSTRAINT `stockhistory_ibfk_1` FOREIGN KEY (`userid`) REFERENCES `users` (`userid`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=539 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `stockhistory`
--

LOCK TABLES `stockhistory` WRITE;
/*!40000 ALTER TABLE `stockhistory` DISABLE KEYS */;
INSERT INTO `stockhistory` VALUES (513,9,'INFY','2025-11-17',17.7),(514,9,'INFY','2025-11-24',17.48),(515,9,'INFY','2025-12-01',18.07),(516,9,'INFY','2025-12-08',17.78),(517,9,'INFY','2025-12-15',20.22),(518,9,'INFY','2025-12-22',18.79),(519,9,'INFY','2025-12-29',18.15),(520,9,'INFY','2026-01-05',17.83),(521,9,'INFY','2026-01-12',18.63),(522,9,'INFY','2026-01-19',18.24),(523,9,'INFY','2026-01-26',17.58),(524,9,'INFY','2026-02-02',16.84),(525,9,'INFY','2026-02-09',14.72),(526,9,'INFY','2026-02-16',14.65),(527,9,'INFY','2026-02-23',14.44),(528,9,'INFY','2026-03-02',14.44),(529,9,'INFY','2026-03-09',13.27),(530,9,'INFY','2026-03-16',13.12),(531,9,'INFY','2026-03-23',12.83),(532,9,'INFY','2026-03-30',13.74),(533,9,'INFY','2026-04-06',13.29),(534,9,'INFY','2026-04-13',14.46),(535,9,'INFY','2026-04-20',12.86),(536,9,'INFY','2026-04-27',12.48),(537,9,'INFY','2026-05-04',12.83),(538,9,'INFY','2026-05-11',12.05);
/*!40000 ALTER TABLE `stockhistory` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `transactionhistory`
--

DROP TABLE IF EXISTS `transactionhistory`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `transactionhistory` (
  `transactionid` int NOT NULL AUTO_INCREMENT,
  `userid` int NOT NULL,
  `portfolioid` int NOT NULL,
  `companyname` varchar(100) NOT NULL,
  `stockname` varchar(100) NOT NULL,
  `quantity` int NOT NULL,
  `price` decimal(12,2) NOT NULL,
  `transactiontype` varchar(10) NOT NULL,
  `timestamp` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`transactionid`),
  KEY `portfolioid` (`portfolioid`),
  KEY `transactionhistory_ibfk_1` (`userid`),
  CONSTRAINT `transactionhistory_ibfk_1` FOREIGN KEY (`userid`) REFERENCES `users` (`userid`) ON DELETE CASCADE,
  CONSTRAINT `transactionhistory_ibfk_2` FOREIGN KEY (`portfolioid`) REFERENCES `portfolio` (`portfolioid`)
) ENGINE=InnoDB AUTO_INCREMENT=237 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `transactionhistory`
--

LOCK TABLES `transactionhistory` WRITE;
/*!40000 ALTER TABLE `transactionhistory` DISABLE KEYS */;
INSERT INTO `transactionhistory` VALUES (204,9,49,'Power Grid Corporation of India Ltd\r','POWERGRID',3,298.05,'BUY','2026-03-16 07:33:35'),(205,9,50,'Axis Bank Ltd\r','AXISBANK',2,1199.80,'BUY','2026-03-16 07:34:11'),(206,9,51,'Reliance Industries Ltd\r','RELIANCE',3,1376.40,'BUY','2026-03-16 07:35:03'),(207,9,51,'Reliance Industries Ltd\r','RELIANCE',2,1376.40,'sell','2026-03-16 07:35:29'),(208,9,50,'Axis Bank Ltd\r','AXISBANK',2,1199.80,'sell','2026-03-16 07:35:41'),(209,9,49,'Power Grid Corporation of India Ltd\r','POWERGRID',3,298.05,'sell','2026-03-16 07:36:10'),(210,9,51,'Reliance Industries Ltd\r','RELIANCE',1,1376.40,'sell','2026-03-16 07:36:16'),(211,9,50,'Axis Bank Ltd\r','AXISBANK',2,1205.20,'BUY','2026-03-29 11:17:00'),(212,9,52,'Apollo Hospitals Enterprise Ltd\r','APOLLOHOSP',1,7549.00,'BUY','2026-03-29 11:17:07'),(213,9,50,'Axis Bank Ltd\r','AXISBANK',1,1205.20,'sell','2026-03-29 11:17:21'),(214,9,52,'Apollo Hospitals Enterprise Ltd\r','APOLLOHOSP',1,7549.00,'sell','2026-03-29 11:18:31'),(215,9,50,'Axis Bank Ltd\r','AXISBANK',1,1205.20,'sell','2026-04-04 04:50:33'),(216,9,50,'Axis Bank Ltd\r','AXISBANK',2,1197.90,'BUY','2026-04-04 11:51:35'),(217,9,53,'Tata Consultancy Services Ltd\r','TCS',1,2576.90,'BUY','2026-04-16 11:45:30'),(218,9,54,'Infosys Ltd\r','INFY',2,1319.20,'BUY','2026-04-16 11:45:39'),(219,9,50,'Axis Bank Ltd\r','AXISBANK',2,1197.90,'sell','2026-04-16 04:45:53'),(220,9,53,'Tata Consultancy Services Limited','TCS',1,2394.40,'buy','2026-05-09 17:00:30'),(221,9,53,'Tata Consultancy Services Ltd\r','TCS',1,2394.40,'sell','2026-05-09 17:01:37'),(222,9,53,'Tata Consultancy Services Limited','TCS',1,2394.40,'buy','2026-05-09 17:02:42'),(223,9,53,'Tata Consultancy Services Ltd\r','TCS',1,2394.40,'sell','2026-05-09 17:03:05'),(224,9,53,'Tata Consultancy Services Ltd\r','TCS',1,2300.30,'buy','2026-05-12 20:23:03'),(225,9,53,'Tata Consultancy Services Ltd\r','TCS',1,2300.30,'sell','2026-05-12 20:23:18'),(226,9,53,'Tata Consultancy Services Ltd\r','TCS',1,2300.30,'BUY','2026-05-12 15:57:03'),(227,9,51,'Reliance Industries Ltd\r','RELIANCE',1,1364.00,'BUY','2026-05-12 15:57:53'),(228,9,51,'Reliance Industries Ltd\r','RELIANCE',1,1364.00,'sell','2026-05-12 21:28:58'),(229,9,55,'HDFC Bank Ltd\r','HDFCBANK',1,750.45,'BUY','2026-05-12 18:18:38'),(230,9,56,'Coal India Ltd\r','COALINDIA',1,463.05,'BUY','2026-05-12 18:25:11'),(231,9,55,'HDFC Bank Ltd\r','HDFCBANK',1,750.45,'sell','2026-05-12 23:59:27'),(232,9,56,'Coal India Ltd\r','COALINDIA',1,463.05,'sell','2026-05-12 23:59:40'),(233,9,57,'Sun Pharmaceutical Industries Ltd\r','SUNPHARMA',1,1845.70,'BUY','2026-05-12 18:30:25'),(234,9,58,'Kotak Mahindra Bank Ltd\r','KOTAKBANK',1,376.00,'BUY','2026-05-12 18:34:13'),(235,9,57,'Sun Pharmaceutical Industries Ltd\r','SUNPHARMA',1,1825.70,'sell','2026-05-13 15:12:42'),(236,9,58,'Kotak Mahindra Bank Ltd\r','KOTAKBANK',2,377.65,'BUY','2026-05-13 11:16:21');
/*!40000 ALTER TABLE `transactionhistory` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `useractivity`
--

DROP TABLE IF EXISTS `useractivity`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `useractivity` (
  `activity_id` int NOT NULL AUTO_INCREMENT,
  `userid` int NOT NULL,
  `activity_type` varchar(50) NOT NULL,
  `activity_value` float DEFAULT '0',
  `activity_date` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`activity_id`),
  KEY `useractivity_ibfk_1` (`userid`),
  CONSTRAINT `useractivity_ibfk_1` FOREIGN KEY (`userid`) REFERENCES `users` (`userid`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=44 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `useractivity`
--

LOCK TABLES `useractivity` WRITE;
/*!40000 ALTER TABLE `useractivity` DISABLE KEYS */;
INSERT INTO `useractivity` VALUES (1,1,'sell',80.24,'2025-09-11 03:10:18'),(4,1,'sell',3124.2,'2025-09-11 03:21:16'),(5,1,'buy',3124.2,'2025-09-11 03:30:48'),(6,1,'buy',3124.2,'2025-09-11 03:30:50'),(7,1,'sell',160.48,'2025-09-11 03:42:13'),(8,1,'sell',6248.4,'2025-09-11 03:42:19'),(9,1,'sell',1004.2,'2025-09-11 03:43:21'),(10,1,'sell',80.24,'2025-09-11 03:43:26'),(11,1,'sell',1004.2,'2025-09-11 03:47:22'),(12,1,'sell',80.24,'2025-09-11 03:47:28'),(13,1,'sell',393.3,'2025-09-11 03:54:25'),(14,1,'sell',2305.6,'2025-09-11 03:54:37'),(15,1,'sell',393.3,'2025-09-11 05:38:04'),(16,1,'sell',152.56,'2025-09-11 05:38:15'),(17,1,'sell',1365,'2025-09-11 05:40:01'),(18,1,'sell',64.35,'2025-09-11 05:40:20'),(19,1,'sell',1973.1,'2025-09-11 05:56:05'),(20,1,'sell',160.48,'2025-09-11 06:19:55'),(21,1,'sell',6248.4,'2025-09-11 06:20:05'),(22,1,'sell',2305.6,'2025-09-11 06:40:08'),(23,1,'sell',1411.2,'2025-09-11 06:40:19'),(24,1,'buy',3124.2,'2025-09-11 11:22:50'),(25,1,'buy',3124.2,'2025-09-11 11:23:18'),(26,1,'sell',3124.2,'2025-09-11 11:50:29'),(27,1,'sell',3124.2,'2025-09-11 12:12:26'),(28,1,'buy',81.01,'2025-09-11 12:12:36'),(29,1,'buy',3133.4,'2025-09-12 10:57:28'),(30,1,'sell',1616.6,'2025-09-13 04:42:40'),(31,1,'sell',1806.1,'2025-10-12 10:20:14'),(32,1,'sell',243.03,'2025-10-12 10:20:22'),(33,1,'sell',3128.8,'2025-10-12 10:23:41'),(34,1,'sell',3133.4,'2025-10-12 10:23:52'),(35,1,'sell',3287.5,'2025-10-12 10:24:00'),(36,1,'sell',3028.3,'2025-10-13 05:02:44'),(37,1,'sell',1357.5,'2025-10-15 05:27:07'),(38,1,'sell',131.28,'2025-10-15 05:28:55'),(39,1,'sell',2344,'2025-10-15 06:45:52'),(40,1,'sell',2969.8,'2025-10-15 06:46:19'),(41,1,'sell',2969.8,'2025-10-15 06:46:23'),(42,1,'sell',134.01,'2025-10-17 04:12:20'),(43,1,'sell',1036.5,'2025-10-17 04:12:26');
/*!40000 ALTER TABLE `useractivity` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `usermilestones`
--

DROP TABLE IF EXISTS `usermilestones`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `usermilestones` (
  `usermilestone_id` int NOT NULL AUTO_INCREMENT,
  `userid` int DEFAULT NULL,
  `milestone_id` int DEFAULT NULL,
  `achieved_on` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`usermilestone_id`),
  KEY `milestone_id` (`milestone_id`),
  KEY `usermilestones_ibfk_1` (`userid`),
  CONSTRAINT `usermilestones_ibfk_1` FOREIGN KEY (`userid`) REFERENCES `users` (`userid`) ON DELETE CASCADE,
  CONSTRAINT `usermilestones_ibfk_2` FOREIGN KEY (`milestone_id`) REFERENCES `milestones` (`milestone_id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `usermilestones`
--

LOCK TABLES `usermilestones` WRITE;
/*!40000 ALTER TABLE `usermilestones` DISABLE KEYS */;
INSERT INTO `usermilestones` VALUES (1,1,1,'2025-09-11 05:06:39'),(2,1,2,'2025-09-11 05:06:39'),(3,1,3,'2025-09-11 07:05:08');
/*!40000 ALTER TABLE `usermilestones` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `userid` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `email` varchar(100) NOT NULL,
  `money` decimal(12,2) DEFAULT '10000.00',
  `profitorloss` decimal(12,2) DEFAULT '0.00',
  `profitpercent` float DEFAULT '0',
  `losspercent` float DEFAULT '0',
  `last_login` datetime DEFAULT NULL,
  `progress` int DEFAULT '0',
  `level` varchar(20) DEFAULT 'Beginner',
  `password_hash` varchar(1024) DEFAULT NULL,
  `otp_code` varchar(10) DEFAULT NULL,
  `otp_ts` datetime DEFAULT NULL,
  PRIMARY KEY (`userid`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'alice','alice@gmail.com',10000.00,0.01,0,0,NULL,0,'Beginner','scrypt:32768:8:1$TbAJPKMhAv1NOfpw$42275916c00af9f22cd957c5738858e52706e4770e7ba12c5e196af99b95895cbc33db8d29b0a476efa8a0e876fe2643bee0ed703ca3a52211514495b0ce8914',NULL,NULL),(2,'hinal dodia','hinaldodia67678@gmail.com',10000.00,0.00,0,0,'2026-01-02 08:16:04',0,'1','scrypt:32768:8:1$67HgRRyqhaNSKTwo$8ad7e209d863affa3910dc0511ad556c770ee627108923956e6d082d4c11852b469300f6b5eb28c8bdc414d4d00f1957e84c31dbfba6cf343809615dbdd2b276',NULL,NULL),(3,'ashwin dodia','ashwindodia1@gmail.com',10000.00,0.00,0,0,'2025-12-29 09:24:52',0,'1','scrypt:32768:8:1$E2BmO8KhEFZLZdA1$ea825b96ca4df0e37d686a0925e1cd2d5b3913bdd966b5b365b01087064ea48a25575bd96fed7365d5a4eb5cdee10b5347aa6390220e791a4c1510ee3175e832',NULL,NULL),(4,'Rohan Dodia','rohandodia1@gmail.com',10000.00,0.00,0,0,'2025-12-29 09:22:56',0,'1','scrypt:32768:8:1$zhaSecTFttnoGsL2$acf7b981d3c84b1a040c87e3b1474e7f1c2f28ecad015ed82d75f777172626bbf1b75363e40d639ab89f092e6bb700938c861f1792ccecd5f7067169c6a34f97',NULL,NULL),(5,'hinal dodia','hinaldodia17@gmail.com',10000.00,0.00,0,0,'2026-01-06 14:43:00',0,'1','scrypt:32768:8:1$Arbjvc7gm7Jwq8R7$a8ab65c6fd2139a5c7fd773c5fc511fcc2f8d74e6e6abcf162f9c57065400abf57f33525a79a0f48f8b8548deb20264123fcff1f56b235ef9d8f581b296aba6e',NULL,NULL),(7,'Rohan Dodia','rohandodia21@gmail.com',10000.00,0.00,0,0,'2026-05-05 11:25:07',0,'1','scrypt:32768:8:1$Pml4z79BbJxtGAjy$01ace4b8bce40d2926d396fa2c9edfb51961dc2b4ebe03c871778514745c2fe1b283c9dba3016bb278cb0741bd72752982c3cb00ab91722f308fdee68990b0b4',NULL,NULL),(9,'Deep Rathod','deeprathod216@gmail.com',1333.10,0.00,0,0,'2026-05-31 10:08:54',0,'1','scrypt:32768:8:1$A1KHVO4fKMrwRiRG$b9f75c2a8b820b30a68302f272a90558ef72788c678d06e6974dd596d6d1bdd516008194ff1011304da291b98f78bf19f28e110342cb88477362c703bc6899f8',NULL,NULL);
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `watchlist`
--

DROP TABLE IF EXISTS `watchlist`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `watchlist` (
  `watchlist_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `stock_id` int NOT NULL,
  PRIMARY KEY (`watchlist_id`),
  KEY `stock_id` (`stock_id`),
  KEY `watchlist_ibfk_1` (`user_id`),
  CONSTRAINT `watchlist_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`userid`) ON DELETE CASCADE,
  CONSTRAINT `watchlist_ibfk_2` FOREIGN KEY (`stock_id`) REFERENCES `stock` (`stock_id`)
) ENGINE=InnoDB AUTO_INCREMENT=122 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `watchlist`
--

LOCK TABLES `watchlist` WRITE;
/*!40000 ALTER TABLE `watchlist` DISABLE KEYS */;
INSERT INTO `watchlist` VALUES (116,9,4127),(118,9,4103),(121,9,4128);
/*!40000 ALTER TABLE `watchlist` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-06-14 20:48:43
