IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'BP2526')
BEGIN
    CREATE DATABASE BP2526;
END
GO

USE BP2526;
GO


IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimDate')
BEGIN
    CREATE TABLE DimDate (
        DateKey INT PRIMARY KEY, 
        FullDateAlternateKey DATE,
        DayOfMonth INT,
        EnglishDayNameOfWeek VARCHAR(50),
        DutchDayNameOfWeek VARCHAR(50),
        DayOfWeek INT,
        DayOfWeekInMonth INT,
        DayOfWeekInYear INT,
        DayOfQuarter INT,
        DayOfYear INT,
        WeekOfMonth INT,
        WeekOfQuarter INT,
        WeekOfYear INT,
        Month INT,
        EnglishMonthName VARCHAR(50),
        DutchMonthName VARCHAR(50),
        MonthOfQuarter INT,
        Quarter INT,
        QuarterName CHAR(2),
        Year INT,
        MonthYear VARCHAR(20),
        MMYYYY CHAR(6),
        IsWeekend BIT,
        IsWorkingDay BIT,
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimTwitterUsers')
BEGIN
-- Tabel: DimTwitterUsers
CREATE TABLE DimTwitterUsers (
    UserID INT PRIMARY KEY,
    userName VARCHAR(100)
);
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimTwitter')
BEGIN
-- Tabel: DimTwitter (Sub-dimensie voor Tweets)
CREATE TABLE DimTwitter (
    TweetID INT PRIMARY KEY,
    userID INT,
    DateKey INT,
    InfluenceScore DECIMAL(10, 2),
    FOREIGN KEY (userID) REFERENCES DimTwitterUsers(UserID),
    FOREIGN KEY (DateKey) REFERENCES DimDate(DateKey)
);

END
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimStock')
BEGIN
-- Tabel: DimStock
CREATE TABLE DimStock (
    StockKey INT PRIMARY KEY,
    StockName VARCHAR(100),
    TypeOfStock VARCHAR(50)
);
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimSource')
BEGIN
-- Tabel: DimSource
CREATE TABLE DimSource (
    SourceKey INT PRIMARY KEY,
    SourceName VARCHAR(100),
    MediaType VARCHAR(50),
    BiasRating VARCHAR(50),
    FactualReportRating VARCHAR(50)
);
END
-- ==========================================
-- 2. Fact Tabellen
-- ==========================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'FactTwitter')
BEGIN
-- Tabel: FactTwitter
CREATE TABLE FactTwitter (
    TweetID INT,
    UserID INT,
    DateKey INT,
    Reposts INT,
    Text TEXT,
    Replies INT,
    Likes INT,
    Bookmarks INT,
    Views INT,
    FOREIGN KEY (TweetID) REFERENCES DimTwitter(TweetID),
    FOREIGN KEY (UserID) REFERENCES DimTwitterUsers(UserID),
    FOREIGN KEY (DateKey) REFERENCES DimDate(DateKey)
);
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'factMarketData')
BEGIN
-- Tabel: FactMarketData
CREATE TABLE FactMarketData (
    DateKey INT,
    StockKey INT,
    [Close] DECIMAL(18, 4),
    High DECIMAL(18, 4),
    Low DECIMAL(18, 4),
    [Open] DECIMAL(18, 4),
    Volume BIGINT,
    Movement_DoD DECIMAL(18, 4),
    FOREIGN KEY (DateKey) REFERENCES DimDate(DateKey),
    FOREIGN KEY (StockKey) REFERENCES DimStock(StockKey)
);
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'FactEcon')
BEGIN
-- Tabel: FactEcon
CREATE TABLE FactEcon (
    EconKey INT PRIMARY KEY,
    DateKey INT,
    USD DECIMAL(18, 4),
    OIL DECIMAL(18, 4),
    GS10 DECIMAL(18, 4),
    GS10_MoM DECIMAL(18, 4),
    GS10_YoY DECIMAL(18, 4),
    GS2 DECIMAL(18, 4),
    GS2_MoM DECIMAL(18, 4),
    GS2_YoY DECIMAL(18, 4),
    GDP DECIMAL(18, 4),
    GDP_MoM DECIMAL(18, 4),
    GDP_YoY DECIMAL(18, 4),
    CPI DECIMAL(18, 4),
    CPI_MoM DECIMAL(18, 4),
    CPI_YoY DECIMAL(18, 4),
    Unemployment DECIMAL(18, 4),
    Unemployment_MoM DECIMAL(18, 4),
    Unemployment_YoY DECIMAL(18, 4),
    PPI DECIMAL(18, 4),
    PPI_MoM DECIMAL(18, 4),
    PPI_YoY DECIMAL(18, 4),
    Personal_Income DECIMAL(18, 4),
    Personal_Income_MoM DECIMAL(18, 4),
    Personal_Income_YoY DECIMAL(18, 4),
    FedFundsRate DECIMAL(18, 4),
    FedFundsRate_Mom DECIMAL(18, 4),
    FedFundsRate_YoY DECIMAL(18, 4),
    Labor_Participation DECIMAL(18, 4),
    Labor_Participation_MoM DECIMAL(18, 4),
    Labor_Participation_YoY DECIMAL(18, 4),
    Employment DECIMAL(18, 4),
    Employment_MoM DECIMAL(18, 4),
    Employment_YoY DECIMAL(18, 4),
    Consumer_Confidence DECIMAL(18, 4),
    Consumer_Confidence_MoM DECIMAL(18, 4),
    Consumer_Confidence_YoY DECIMAL(18, 4),
    FOREIGN KEY (DateKey) REFERENCES DimDate(DateKey)
);
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'FactNews')
BEGIN
-- Tabel: FactNews
CREATE TABLE FactNews (
    NewsKey INT PRIMARY KEY,
    DateKey INT,
    SourceKey INT,
    Headline VARCHAR(500),
    Abstract TEXT,
    Section VARCHAR(100),
    Web_url VARCHAR(500),
    FOREIGN KEY (DateKey) REFERENCES DimDate(DateKey),
    FOREIGN KEY (SourceKey) REFERENCES DimSource(SourceKey)
);
END