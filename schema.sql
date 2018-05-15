CREATE TABLE `cycletime` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `date` date NOT NULL,
  `cos` varchar(255) DEFAULT NULL,
  `cycletime` decimal(10,2) unsigned NOT NULL,
  `throughput` int(10) unsigned DEFAULT NULL,
  `in_progress` decimal(10,2) unsigned DEFAULT NULL,
  `inactive` decimal(10,2) unsigned DEFAULT NULL,
  `flagged` decimal(10,2) unsigned DEFAULT NULL,
  `total` decimal(10,2) unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `date` (`date`,`cos`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;