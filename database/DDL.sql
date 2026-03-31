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
-- 1. STAGING TABELLEN (raw CSV data, alles VARCHAR)
--    Naamconventie: stg_*
--    - Geen FK constraints
--    - Alles VARCHAR om laadfouten te vermijden
--    - LoadedAt en SourceFile voor traceerbaarheid
-- ==========================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'stg_Date')
BEGIN
    CREATE TABLE stg_Date (
        DateKey             VARCHAR(50),
        FullDateAlternateKey VARCHAR(50),
        DayOfMonth          VARCHAR(50),
        EnglishDayNameOfWeek VARCHAR(50),
        DutchDayNameOfWeek  VARCHAR(50),
        DayOfWeek           VARCHAR(50),
        DayOfWeekInMonth    VARCHAR(50),
        DayOfWeekInYear     VARCHAR(50),
        DayOfQuarter        VARCHAR(50),
        DayOfYear           VARCHAR(50),
        WeekOfMonth         VARCHAR(50),
        WeekOfQuarter       VARCHAR(50),
        WeekOfYear          VARCHAR(50),
        Month               VARCHAR(50),
        EnglishMonthName    VARCHAR(50),
        DutchMonthName      VARCHAR(50),
        MonthOfQuarter      VARCHAR(50),
        Quarter             VARCHAR(50),
        QuarterName         VARCHAR(50),
        Year                VARCHAR(50),
        MonthYear           VARCHAR(50),
        MMYYYY              VARCHAR(50),
        IsWeekend           VARCHAR(50),
        IsWorkingDay        VARCHAR(50),
        LoadedAt            DATETIME DEFAULT GETDATE(),
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'stg_TwitterUsers')
BEGIN
    CREATE TABLE stg_TwitterUsers (
        UserID      VARCHAR(50),
        UserName    VARCHAR(100),
        LoadedAt    DATETIME DEFAULT GETDATE(),
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'stg_Twitter')
BEGIN
    CREATE TABLE stg_Twitter (
        TweetID         VARCHAR(50),
        UserID          VARCHAR(50),
        DateKey         VARCHAR(50),
        Reposts         VARCHAR(50),
        Text            VARCHAR(MAX),
        Replies         VARCHAR(50),
        Likes           VARCHAR(50),
        Bookmarks       VARCHAR(50),
        Views           VARCHAR(50),
        InfluenceScore  VARCHAR(50),
        LoadedAt        DATETIME DEFAULT GETDATE(),
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'stg_Stock')
BEGIN
    CREATE TABLE stg_Stock (
        StockKey    VARCHAR(50),
        StockName   VARCHAR(100),
        TypeOfStock VARCHAR(50),
        LoadedAt    DATETIME DEFAULT GETDATE(),
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'stg_Source')
BEGIN
    CREATE TABLE stg_Source (
        SourceKey           VARCHAR(50),
        SourceName          VARCHAR(100),
        MediaType           VARCHAR(50),
        BiasRating          VARCHAR(50),
        FactualReportRating VARCHAR(50),
        LoadedAt            DATETIME DEFAULT GETDATE(),
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'stg_MarketData')
BEGIN
    CREATE TABLE stg_MarketData (
        DateKey         VARCHAR(50),
        StockKey        VARCHAR(50),
        StockName       VARCHAR(100),
        [Close]         VARCHAR(50),
        High            VARCHAR(50),
        Low             VARCHAR(50),
        [Open]          VARCHAR(50),
        Volume          VARCHAR(50),
        Movement_DoD    VARCHAR(50),
        LoadedAt        DATETIME DEFAULT GETDATE(),
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'stg_EconData')
BEGIN
    CREATE TABLE stg_EconData (
        EconKey                 VARCHAR(50),
        DateKey                 VARCHAR(50),
        USD                     VARCHAR(50),
        OIL                     VARCHAR(50),
        GS10                    VARCHAR(50),
        GS10_MoM                VARCHAR(50),
        GS10_YoY                VARCHAR(50),
        GS2                     VARCHAR(50),
        GS2_MoM                 VARCHAR(50),
        GS2_YoY                 VARCHAR(50),
        GDP                     VARCHAR(50),
        GDP_MoM                 VARCHAR(50),
        GDP_YoY                 VARCHAR(50),
        CPI                     VARCHAR(50),
        CPI_MoM                 VARCHAR(50),
        CPI_YoY                 VARCHAR(50),
        Unemployment            VARCHAR(50),
        Unemployment_MoM        VARCHAR(50),
        Unemployment_YoY        VARCHAR(50),
        PPI                     VARCHAR(50),
        PPI_MoM                 VARCHAR(50),
        PPI_YoY                 VARCHAR(50),
        Personal_Income         VARCHAR(50),
        Personal_Income_MoM     VARCHAR(50),
        Personal_Income_YoY     VARCHAR(50),
        FedFundsRate            VARCHAR(50),
        FedFundsRate_MoM        VARCHAR(50),
        FedFundsRate_YoY        VARCHAR(50),
        Labor_Participation     VARCHAR(50),
        Labor_Participation_MoM VARCHAR(50),
        Labor_Participation_YoY VARCHAR(50),
        Employment              VARCHAR(50),
        Employment_MoM          VARCHAR(50),
        Employment_YoY          VARCHAR(50),
        Consumer_Confidence     VARCHAR(50),
        Consumer_Confidence_MoM VARCHAR(50),
        Consumer_Confidence_YoY VARCHAR(50),
        LoadedAt                DATETIME DEFAULT GETDATE(),
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'stg_News')
BEGIN
    CREATE TABLE stg_News (
        NewsKey     VARCHAR(50),
        DateKey     VARCHAR(50),
        SourceKey   VARCHAR(50),
        SourceName  VARCHAR(100),
        Headline    VARCHAR(500),
        Abstract    VARCHAR(MAX),
        Section     VARCHAR(100),
        Web_url     VARCHAR(500),
        LoadedAt    DATETIME DEFAULT GETDATE(),
    );
END


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
        Month                   INT,
        EnglishMonthName        VARCHAR(50),
        DutchMonthName          VARCHAR(50),
        MonthOfQuarter          INT,
        Quarter                 INT,
        QuarterName             CHAR(2),
        Year                    INT,
        MonthYear               VARCHAR(20),
        MMYYYY                  CHAR(6),
        IsWeekend               BIT,
        IsWorkingDay            BIT
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimTwitterUsers')
BEGIN
    CREATE TABLE DimTwitterUsers (
        UserID      INT PRIMARY KEY,
        UserName    VARCHAR(100)
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimTwitter')
BEGIN
    CREATE TABLE DimTwitter (
        TweetID         INT PRIMARY KEY,
        UserID          INT,
        DateKey         INT,
        InfluenceScore  DECIMAL(10, 2),
        FOREIGN KEY (UserID)  REFERENCES DimTwitterUsers(UserID),
        FOREIGN KEY (DateKey) REFERENCES DimDate(DateKey)
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimStock')
BEGIN
    CREATE TABLE DimStock (
        StockKey    INT PRIMARY KEY,
        StockName   VARCHAR(100),
        TypeOfStock VARCHAR(50)
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'DimSource')
BEGIN
    CREATE TABLE DimSource (
        SourceKey           INT PRIMARY KEY,
        SourceName          VARCHAR(100),
        MediaType           VARCHAR(50),
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
        DateKey     INT,
        Reposts     INT,
        Text        TEXT,
        Replies     INT,
        Likes       INT,
        Bookmarks   INT,
        Views       INT,
        FOREIGN KEY (TweetID) REFERENCES DimTwitter(TweetID),
        FOREIGN KEY (UserID)  REFERENCES DimTwitterUsers(UserID),
        FOREIGN KEY (DateKey) REFERENCES DimDate(DateKey)
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'FactMarketData')
BEGIN
    CREATE TABLE FactMarketData (
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
        EconKey                 INT PRIMARY KEY,
        DateKey                 INT,
        USD                     DECIMAL(18, 4),
        OIL                     DECIMAL(18, 4),
        GS10                    DECIMAL(18, 4),
        GS10_MoM                DECIMAL(18, 4),
        GS10_YoY                DECIMAL(18, 4),
        GS2                     DECIMAL(18, 4),
        GS2_MoM                 DECIMAL(18, 4),
        GS2_YoY                 DECIMAL(18, 4),
        GDP                     DECIMAL(18, 4),
        GDP_MoM                 DECIMAL(18, 4),
        GDP_YoY                 DECIMAL(18, 4),
        CPI                     DECIMAL(18, 4),
        CPI_MoM                 DECIMAL(18, 4),
        CPI_YoY                 DECIMAL(18, 4),
        Unemployment            DECIMAL(18, 4),
        Unemployment_MoM        DECIMAL(18, 4),
        Unemployment_YoY        DECIMAL(18, 4),
        PPI                     DECIMAL(18, 4),
        PPI_MoM                 DECIMAL(18, 4),
        PPI_YoY                 DECIMAL(18, 4),
        Personal_Income         DECIMAL(18, 4),
        Personal_Income_MoM     DECIMAL(18, 4),
        Personal_Income_YoY     DECIMAL(18, 4),
        FedFundsRate            DECIMAL(18, 4),
        FedFundsRate_MoM        DECIMAL(18, 4),
        FedFundsRate_YoY        DECIMAL(18, 4),
        Labor_Participation     DECIMAL(18, 4),
        Labor_Participation_MoM DECIMAL(18, 4),
        Labor_Participation_YoY DECIMAL(18, 4),
        Employment              DECIMAL(18, 4),
        Employment_MoM          DECIMAL(18, 4),
        Employment_YoY          DECIMAL(18, 4),
        Consumer_Confidence     DECIMAL(18, 4),
        Consumer_Confidence_MoM DECIMAL(18, 4),
        Consumer_Confidence_YoY DECIMAL(18, 4),
        FOREIGN KEY (DateKey) REFERENCES DimDate(DateKey)
    );
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'FactNews')
BEGIN
    CREATE TABLE FactNews (
        NewsKey     INT PRIMARY KEY,
        DateKey     INT,
        SourceKey   INT,
        Headline    VARCHAR(500),
        Abstract    TEXT,
        Section     VARCHAR(100),
        Web_url     VARCHAR(500),
        FOREIGN KEY (DateKey)   REFERENCES DimDate(DateKey),
        FOREIGN KEY (SourceKey) REFERENCES DimSource(SourceKey)
    );
END