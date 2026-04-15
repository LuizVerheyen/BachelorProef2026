-- ==========================================
-- DATABASE: BP2526
-- DDL Script met Staging + Dimensie + Fact tabellen
-- ==========================================

IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'BP2526')
BEGIN
    CREATE DATABASE BP2526;
END
GO

USE BP2526;
GO


-- ==========================================
-- 2. DIMENSIE TABELLEN (getypeerd, gecleaned)
-- ==========================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimDate')
BEGIN
    CREATE TABLE DimDate (
        DateKey                 INT PRIMARY KEY,
        FullDateAlternateKey    DATE,
        DayOfMonth              INT,
        EnglishDayNameOfWeek    VARCHAR(50),
        DutchDayNameOfWeek      VARCHAR(50),
        DayOfWeek               INT,
        DayOfWeekInMonth        INT,
        DayOfWeekInYear         INT,
        DayOfQuarter            INT,
        DayOfYear               INT,
        WeekOfMonth             INT,
        WeekOfQuarter           INT,
        WeekOfYear              INT,
        [Month]                   INT,
        EnglishMonthName        VARCHAR(50),
        DutchMonthName          VARCHAR(50),
        MonthOfQuarter          INT,
        Quarter                 INT,
        QuarterName             CHAR(2),
        [Year]                    INT,
        MonthYear               VARCHAR(20),
        MMYYYY                  CHAR(6),
        IsWeekend               BIT,
        IsWorkingDay            BIT
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimTime')
BEGIN
    CREATE TABLE DimTime (
        TimeKey     INT           NOT NULL,
        FullTime    TIME          NOT NULL,
        Hour        TINYINT       NOT NULL,
        Minute      TINYINT       NOT NULL,
        Second      TINYINT       NOT NULL,
        AMPM        CHAR(2)       NOT NULL,
        Hour12      TINYINT       NOT NULL,

        CONSTRAINT PK_DimTime PRIMARY KEY (TimeKey)
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimTwitterUsers')
BEGIN
    CREATE TABLE DimTwitterUsers (
        UserID      INT IDENTITY (1,1) PRIMARY KEY,
        UserName    VARCHAR(100),
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimTwitter')
BEGIN
    CREATE TABLE DimTwitter (
        TweetID         INT IDENTITY (1,1) PRIMARY KEY,
        UserID          INT,
        DateKey         INT,
        [Text]            VARCHAR(MAX)
        FOREIGN KEY (UserID)  REFERENCES DimTwitterUsers(UserID),
        FOREIGN KEY (DateKey) REFERENCES DimDate(DateKey)
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimStock')
BEGIN
    CREATE TABLE DimStock (
        StockKey    VARCHAR(10) PRIMARY KEY,
        StockName   VARCHAR(100),
        [Type] VARCHAR(50)
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimSource')
BEGIN
    CREATE TABLE DimSource (
        SourceKey           INT IDENTITY (1,1) PRIMARY KEY,
        SourceName          VARCHAR(100),
        BiasRating          VARCHAR(50),
        FactualReportRating VARCHAR(50)
    );
END


-- ==========================================
-- 3. FACT TABELLEN
-- ==========================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'FactTwitter')
BEGIN
    CREATE TABLE FactTwitter (
        TweetID     INT,
        UserID      INT,
        Comments    INT,
        Likes       INT,
        Reposts     INT,
        -- Views       INT, kan niet voor truthsocial
        CONSTRAINT PK_FactTwitter PRIMARY KEY (tweetID),
        FOREIGN KEY (TweetID) REFERENCES DimTwitter(TweetID),
        FOREIGN KEY (UserID)  REFERENCES DimTwitterUsers(UserID),
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'FactMarketData')
BEGIN
    CREATE TABLE FactMarketData (
        MarketKey       INT IDENTITY (1,1) PRIMARY KEY,
        DateKey         INT,
        StockKey        INT,
        [Close]         DECIMAL(18, 4),
        High            DECIMAL(18, 4),
        Low             DECIMAL(18, 4),
        [Open]          DECIMAL(18, 4),
        Volume          BIGINT,
        Movement_DoD    DECIMAL(18, 4),
        FOREIGN KEY (DateKey)  REFERENCES DimDate(DateKey),
        FOREIGN KEY (StockKey) REFERENCES DimStock(StockKey)
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'FactEcon')
BEGIN
    CREATE TABLE FactEcon (
        EconKey                 INT IDENTITY (1,1) PRIMARY KEY,
        DateKey                 INT,
        USD                     DECIMAL(18, 4),
        OIL                     DECIMAL(18, 4),
        CPI                     DECIMAL(18, 4),
        VIX                     DECIMAL(18, 4),
        YieldSpread             DECIMAL(18, 4),
        InfExpectation          DECIMAL(18, 4),
        FinStress               DECIMAL(18, 4),
        FedFundsRate            DECIMAL(18, 4),
        FedBalanceSheet         DECIMAL(18, 4),
        CPI                     DECIMAL(18, 4),
        PPI                     DECIMAL(18, 4),
        Consumer_Confidence     DECIMAL(18, 4),
        FOREIGN KEY (DateKey) REFERENCES DimDate(DateKey)
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'FactNews')
BEGIN
    CREATE TABLE FactNews (
        NewsKey     INT IDENTITY (1,1) PRIMARY KEY,
        DateKey     INT,
        SourceKey   INT,
        Headline    VARCHAR(MAX),
        Abstract    VARCHAR(MAX),
        Section     VARCHAR(100),
        [URL] VARCHAR(2048)
        FOREIGN KEY (DateKey)   REFERENCES DimDate(DateKey),
        FOREIGN KEY (SourceKey) REFERENCES DimSource(SourceKey)
    );
END