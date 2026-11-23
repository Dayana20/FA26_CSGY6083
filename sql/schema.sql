-- Cruise Trip Booking schema for MySQL 8 / MariaDB 10.4+ (XAMPP).
--
-- Converted from the Oracle SQL Developer Data Modeler export (2026-11-04), with:
--   * ADH_STATEROOM_TYPE added: size, beds, bathrooms and balconies now live on
--     the type, and each stateroom references its type.
--   * Additional CHECK constraints for formats (email, phone, state, zip) and
--     ranges (positive counts, non-negative money, end dates after start dates).
--   * ADH_USER_ACCOUNT added for app logins (passwords stored only as hashes).
--   * A stateroom can be booked only once per trip; every booking, trip and
--     port stop must name its stateroom, ship and port.
--   * Customer STATE and ZIPCODE are optional; customer STREET widened to 100.
--   * ADH_PORT.STATE and ZIPCODE are optional (ports outside the US have
--     neither); ADH_BOOKING.STATEROOM_PRICE_PER_NIGHT widened to DECIMAL(8,2).
--   * Code columns (STATE, GENDER, RATE_TYPE, PAYMENT_METHOD) use a case-sensitive collation so
--     their checks only accept uppercase.
--   * Oracle-only syntax replaced: NUMBER -> INT/SMALLINT/DECIMAL,
--     VARCHAR2 -> VARCHAR, COMMENT ON COLUMN -> inline COMMENT, restaurant
--     opening/closing times DATE -> TIME.
--   * The ALTER TABLE statements at the end of the original folded into the
--     CREATE TABLE statements.
--
-- Rows can't be deleted through the app: its MySQL user is only granted
-- SELECT, INSERT and UPDATE (see app/database/init_db.py), and foreign keys
-- block deleting any row other rows still reference.
--
-- Tables are created parents first so every FOREIGN KEY target already exists.
-- Run through the setup script: python -m app.database.init_db
-- See docs/database.md for a description of every table and column.


-- ---------------------------------------------------------------------------
-- Groups and customers
-- ---------------------------------------------------------------------------

CREATE TABLE ADH_GROUP (
    GROUP_ID INT NOT NULL AUTO_INCREMENT COMMENT 'Group ID',
    CONSTRAINT ADH_GROUP_PK PRIMARY KEY (GROUP_ID)
) COMMENT = 'A travel party; bookings are made per group';

CREATE TABLE ADH_CUSTOMER (
    CUSTOMER_ID INT          NOT NULL AUTO_INCREMENT COMMENT 'Passenger ID',
    F_NAME      VARCHAR(30)  NOT NULL COMMENT 'Customer first name',
    L_NAME      VARCHAR(30)  NOT NULL COMMENT 'Customer last name',
    DOB         DATE         NOT NULL COMMENT 'Customer date of birth',
    STREET      VARCHAR(100) NOT NULL COMMENT 'Street address',
    CITY        VARCHAR(30)  NOT NULL COMMENT 'Address city',
    STATE       VARCHAR(2)   COLLATE utf8mb4_bin COMMENT 'Address state (2-letter code, optional)',
    ZIPCODE     VARCHAR(5)            COMMENT 'Zipcode (5 digits, optional)',
    COUNTRY     VARCHAR(30)  NOT NULL COMMENT 'Address country',
    GENDER      VARCHAR(1)   COLLATE utf8mb4_bin COMMENT 'Gender: M, F or X (optional)',
    NATIONALITY VARCHAR(30)  NOT NULL COMMENT 'Customer nationality',
    EMAIL       VARCHAR(50)  NOT NULL COMMENT 'Customer email',
    PHONE       VARCHAR(20)  NOT NULL COMMENT 'Customer phone number',
    GROUP_ID    INT          NOT NULL COMMENT 'Group ID',
    CONSTRAINT ADH_CUSTOMER_PK PRIMARY KEY (CUSTOMER_ID),
    CONSTRAINT ADH_CUSTOMER_GROUP_FK FOREIGN KEY (GROUP_ID)
        REFERENCES ADH_GROUP (GROUP_ID),
    CONSTRAINT C_CUSTOMER_F_NAME CHECK (TRIM(F_NAME) <> ''),
    CONSTRAINT C_CUSTOMER_L_NAME CHECK (TRIM(L_NAME) <> ''),
    CONSTRAINT C_CUSTOMER_DOB CHECK (DOB >= '1900-01-01'),
    CONSTRAINT C_CUSTOMER_STATE CHECK (STATE REGEXP '^[A-Z]{2}$'),
    CONSTRAINT C_CUSTOMER_ZIP CHECK (ZIPCODE REGEXP '^[0-9]{5}$'),
    CONSTRAINT C_CUSTOMER_GENDER CHECK (GENDER IN ('M', 'F', 'X')),
    CONSTRAINT C_CUSTOMER_EMAIL CHECK (EMAIL REGEXP '^[^@ ]+@[^@ ]+[.][^@ ]+$'),
    CONSTRAINT C_CUSTOMER_PHONE CHECK (PHONE REGEXP '^[+]?[0-9][0-9 ().-]{6,19}$')
) COMMENT = 'A passenger; every customer belongs to one group';


CREATE TABLE ADH_USER_ACCOUNT (
    USER_ID       INT          NOT NULL AUTO_INCREMENT COMMENT 'User account ID',
    USERNAME      VARCHAR(30)  NOT NULL COMMENT 'Login name',
    PASSWORD_HASH VARCHAR(255) NOT NULL COMMENT 'Password hash (bcrypt or argon2), never the plain password',
    ROLE          VARCHAR(10)  COLLATE utf8mb4_bin NOT NULL DEFAULT 'CUSTOMER' COMMENT 'CUSTOMER or ADMIN',
    CUSTOMER_ID   INT                   COMMENT 'Customer this login belongs to (required for CUSTOMER)',
    CREATED_AT    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'When the account was created',
    LAST_LOGIN_AT DATETIME              COMMENT 'Most recent successful login',
    CONSTRAINT ADH_USER_ACCOUNT_PK PRIMARY KEY (USER_ID),
    CONSTRAINT ADH_USER_ACCOUNT_USERNAME_UK UNIQUE (USERNAME),
    CONSTRAINT ADH_USER_ACCOUNT_CUSTOMER_UK UNIQUE (CUSTOMER_ID),
    CONSTRAINT ADH_USER_ACCOUNT_CUSTOMER_FK FOREIGN KEY (CUSTOMER_ID)
        REFERENCES ADH_CUSTOMER (CUSTOMER_ID),
    CONSTRAINT C_USER_USERNAME CHECK (USERNAME REGEXP '^[A-Za-z0-9_.-]{3,30}$'),
    CONSTRAINT C_USER_PASSWORD_HASH CHECK (CHAR_LENGTH(PASSWORD_HASH) >= 60),
    CONSTRAINT C_USER_ROLE CHECK (ROLE IN ('CUSTOMER', 'ADMIN')),
    CONSTRAINT C_USER_CUSTOMER CHECK (ROLE = 'ADMIN' OR CUSTOMER_ID IS NOT NULL)
) COMMENT = 'A login for the demo app: a customer, or an admin with no customer record';


-- ---------------------------------------------------------------------------
-- Ships and what is on them
-- ---------------------------------------------------------------------------

CREATE TABLE ADH_CRUISE_SHIP (
    SHIP_ID      INT         NOT NULL AUTO_INCREMENT COMMENT 'Cruise ship id',
    SHIP_NAME    VARCHAR(30) NOT NULL COMMENT 'Cruise ship name',
    NO_OF_FLOORS SMALLINT    NOT NULL COMMENT 'Number of floors in cruise ship',
    CONSTRAINT ADH_CRUISE_SHIP_PK PRIMARY KEY (SHIP_ID),
    CONSTRAINT C_CRUISE_SHIP_NAME CHECK (TRIM(SHIP_NAME) <> ''),
    CONSTRAINT C_CRUISE_SHIP_NO_FLOORS CHECK (NO_OF_FLOORS BETWEEN 1 AND 99)
) COMMENT = 'A cruise ship';

CREATE TABLE ADH_CRUISE_SHIP_PART (
    CS_PART_ID   INT          NOT NULL AUTO_INCREMENT COMMENT 'Part ID',
    CS_PART_NAME VARCHAR(30)  NOT NULL COMMENT 'Cruise ship part name',
    DESCRIPTION  VARCHAR(100) NOT NULL COMMENT 'Cruise ship part description',
    CONSTRAINT ADH_CRUISE_SHIP_PART_PK PRIMARY KEY (CS_PART_ID),
    CONSTRAINT C_CS_PART_NAME CHECK (TRIM(CS_PART_NAME) <> '')
) COMMENT = 'A section of a ship (e.g. forward, mid, aft) that staterooms are in';

CREATE TABLE ADH_STATEROOM_TYPE (
    SR_TYPE_ID   INT         NOT NULL AUTO_INCREMENT COMMENT 'Stateroom type ID',
    SR_TYPE_NAME VARCHAR(30) NOT NULL COMMENT 'Stateroom type name',
    `SIZE`       SMALLINT    NOT NULL COMMENT 'Stateroom size',
    NO_BEDS      SMALLINT    NOT NULL COMMENT 'Bed count',
    NO_BATHROOMS SMALLINT    NOT NULL COMMENT 'Bathroom count',
    BALCONY      SMALLINT    NOT NULL COMMENT 'Balcony count',
    CONSTRAINT ADH_STATEROOM_TYPE_PK PRIMARY KEY (SR_TYPE_ID),
    CONSTRAINT ADH_STATEROOM_TYPE_NAME_UK UNIQUE (SR_TYPE_NAME),
    CONSTRAINT C_SR_TYPE_NAME CHECK (TRIM(SR_TYPE_NAME) <> ''),
    CONSTRAINT C_SR_TYPE_SIZE CHECK (`SIZE` > 0),
    CONSTRAINT C_SR_TYPE_BEDS CHECK (NO_BEDS BETWEEN 1 AND 99),
    CONSTRAINT C_SR_TYPE_BATHROOMS CHECK (NO_BATHROOMS BETWEEN 1 AND 99),
    CONSTRAINT C_SR_TYPE_BALCONY CHECK (BALCONY BETWEEN 0 AND 99)
) COMMENT = 'A kind of stateroom; size and amenities shared by every room of that kind';

CREATE TABLE ADH_STATEROOM (
    STATEROOM_ID INT NOT NULL AUTO_INCREMENT COMMENT 'Stateroom ID',
    SR_TYPE_ID   INT NOT NULL COMMENT 'Stateroom type ID',
    CS_PART_ID   INT NOT NULL COMMENT 'Cruise ship part id',
    SHIP_ID      INT NOT NULL COMMENT 'Cruise ship id',
    CONSTRAINT ADH_STATEROOM_PK PRIMARY KEY (STATEROOM_ID),
    CONSTRAINT ADH_STATEROOM_TYPE_FK FOREIGN KEY (SR_TYPE_ID)
        REFERENCES ADH_STATEROOM_TYPE (SR_TYPE_ID),
    CONSTRAINT ADH_STATEROOM_CS_PART_FK FOREIGN KEY (CS_PART_ID)
        REFERENCES ADH_CRUISE_SHIP_PART (CS_PART_ID),
    CONSTRAINT ADH_STATEROOM_CS_FK FOREIGN KEY (SHIP_ID)
        REFERENCES ADH_CRUISE_SHIP (SHIP_ID)
) COMMENT = 'A bookable room on a ship';

CREATE TABLE ADH_ACTIVITY (
    ACTIVITY_ID   INT         NOT NULL AUTO_INCREMENT COMMENT 'Activity ID',
    ACTIVITY_NAME VARCHAR(30) NOT NULL COMMENT 'Activity name',
    CONSTRAINT ADH_ACTIVITY_PK PRIMARY KEY (ACTIVITY_ID),
    CONSTRAINT ADH_ACTIVITY_NAME_UK UNIQUE (ACTIVITY_NAME),
    CONSTRAINT C_ACTIVITY_NAME CHECK (TRIM(ACTIVITY_NAME) <> '')
) COMMENT = 'A kind of onboard activity (e.g. pool, casino, theater)';

CREATE TABLE ADH_SHIP_ACTIVITY (
    FLOOR       SMALLINT NOT NULL COMMENT 'Floor number',
    NO_UNITS    SMALLINT NOT NULL COMMENT 'Units count',
    SHIP_ID     INT      NOT NULL COMMENT 'Cruise ship ID',
    ACTIVITY_ID INT      NOT NULL COMMENT 'Activity ID',
    CONSTRAINT ADH_SHIP_ACTIVITY_PK PRIMARY KEY (SHIP_ID, ACTIVITY_ID, FLOOR),
    CONSTRAINT ADH_SHIP_ACTIVITY_CS_FK FOREIGN KEY (SHIP_ID)
        REFERENCES ADH_CRUISE_SHIP (SHIP_ID),
    CONSTRAINT ADH_SHIP_ACTIVITY_FK FOREIGN KEY (ACTIVITY_ID)
        REFERENCES ADH_ACTIVITY (ACTIVITY_ID),
    CONSTRAINT C_SHIP_ACTIVITY_FLOOR CHECK (FLOOR BETWEEN 1 AND 99),
    CONSTRAINT C_SHIP_ACTIVITY_UNITS CHECK (NO_UNITS BETWEEN 1 AND 99)
) COMMENT = 'Which activities a ship has, on which floor, and how many';

CREATE TABLE ADH_RESTAURANT (
    RESTAURANT_ID   INT         NOT NULL AUTO_INCREMENT COMMENT 'Restaurant ID',
    RESTAURANT_NAME VARCHAR(30) NOT NULL COMMENT 'Restaurant name',
    MEAL_TYPE       VARCHAR(30) NOT NULL COMMENT 'Meal type',
    OPEN_TIME       TIME        NOT NULL COMMENT 'Opening time',
    CLOSING_TIME    TIME        NOT NULL COMMENT 'Closing time',
    FLOOR           SMALLINT    NOT NULL COMMENT 'Restaurant floor',
    SHIP_ID         INT         NOT NULL COMMENT 'Cruise ship id',
    CONSTRAINT ADH_RESTAURANT_PK PRIMARY KEY (RESTAURANT_ID),
    CONSTRAINT ADH_RESTAURANT_CS_FK FOREIGN KEY (SHIP_ID)
        REFERENCES ADH_CRUISE_SHIP (SHIP_ID),
    CONSTRAINT C_RESTAURANT_NAME CHECK (TRIM(RESTAURANT_NAME) <> ''),
    CONSTRAINT C_RESTAURANT_MEAL_TYPE CHECK (TRIM(MEAL_TYPE) <> ''),
    CONSTRAINT C_RESTAURANT_HOURS CHECK (OPEN_TIME <> CLOSING_TIME),
    CONSTRAINT C_RESTAURANT_FLOOR CHECK (FLOOR BETWEEN 1 AND 99)
) COMMENT = 'A restaurant on a ship';


-- ---------------------------------------------------------------------------
-- Ports and trips
-- ---------------------------------------------------------------------------

CREATE TABLE ADH_PORT (
    PORT_ID          INT          NOT NULL AUTO_INCREMENT COMMENT 'Port id',
    PORT_NAME        VARCHAR(100) NOT NULL COMMENT 'Port name',
    STREET           VARCHAR(150) NOT NULL COMMENT 'Port street address',
    CITY             VARCHAR(100) NOT NULL COMMENT 'City',
    STATE            VARCHAR(2)   COLLATE utf8mb4_bin COMMENT 'Port state address (2-letter code, optional)',
    ZIPCODE          VARCHAR(5)            COMMENT 'Numeric zipcode (5 digits, optional)',
    COUNTRY          VARCHAR(30)  NOT NULL COMMENT 'Port country',
    NEAREST_AIRPORT  VARCHAR(50)  NOT NULL COMMENT 'Name of nearest airport',
    PARKING_CAPACITY SMALLINT              COMMENT 'Parking capacity (optional)',
    CONSTRAINT ADH_PORT_PK PRIMARY KEY (PORT_ID),
    CONSTRAINT C_PORT_NAME CHECK (TRIM(PORT_NAME) <> ''),
    CONSTRAINT C_PORT_STATE CHECK (STATE REGEXP '^[A-Z]{2}$'),
    CONSTRAINT C_PORT_ZIP CHECK (ZIPCODE REGEXP '^[0-9]{5}$'),
    CONSTRAINT C_PORT_PARKING CHECK (PARKING_CAPACITY BETWEEN 0 AND 999)
) COMMENT = 'A port where trips stop';

CREATE TABLE ADH_TRIP (
    TRIP_ID    INT  NOT NULL AUTO_INCREMENT COMMENT 'Trip ID',
    START_DATE DATE NOT NULL COMMENT 'Start date',
    END_DATE   DATE NOT NULL COMMENT 'End date',
    SHIP_ID    INT  NOT NULL COMMENT 'Cruise ship id',
    CONSTRAINT ADH_TRIP_PK PRIMARY KEY (TRIP_ID),
    CONSTRAINT ADH_TRIP_CS_FK FOREIGN KEY (SHIP_ID)
        REFERENCES ADH_CRUISE_SHIP (SHIP_ID),
    CONSTRAINT C_TRIP_DATES CHECK (END_DATE > START_DATE)
) COMMENT = 'A cruise: one ship sailing between two dates';

CREATE TABLE ADH_PORT_STOP (
    STOP_NO     SMALLINT NOT NULL COMMENT 'Order of stop in trip',
    PSTART_DATE DATE     NOT NULL COMMENT 'Port start date',
    PEND_DATE   DATE     NOT NULL COMMENT 'Port end date',
    TRIP_ID     INT      NOT NULL COMMENT 'trip id',
    PORT_ID     INT      NOT NULL COMMENT 'port id',
    CONSTRAINT ADH_PORT_STOP_PK PRIMARY KEY (STOP_NO, TRIP_ID),
    CONSTRAINT ADH_PORT_STOP_TRIP_FK FOREIGN KEY (TRIP_ID)
        REFERENCES ADH_TRIP (TRIP_ID),
    CONSTRAINT ADH_PORT_STOP_PORT_FK FOREIGN KEY (PORT_ID)
        REFERENCES ADH_PORT (PORT_ID),
    CONSTRAINT C_PORT_STOP_NO CHECK (STOP_NO >= 1),
    CONSTRAINT C_PORT_STOP_DATES CHECK (PEND_DATE >= PSTART_DATE)
) COMMENT = 'One stop on a trip itinerary, in order';


-- ---------------------------------------------------------------------------
-- Bookings, packages and payments
-- ---------------------------------------------------------------------------

CREATE TABLE ADH_PACKAGE (
    PACKAGE_ID   INT           NOT NULL AUTO_INCREMENT COMMENT 'Package ID',
    PACKAGE_NAME VARCHAR(30)   NOT NULL COMMENT 'Package name',
    RATE         DECIMAL(10,2) NOT NULL COMMENT 'Package rate',
    RATE_TYPE    VARCHAR(1)    COLLATE utf8mb4_bin NOT NULL COMMENT 'Rate type if per night (N) or trip (T)',
    CONSTRAINT ADH_PACKAGE_PK PRIMARY KEY (PACKAGE_ID),
    CONSTRAINT ADH_PACKAGE_NAME_UK UNIQUE (PACKAGE_NAME),
    CONSTRAINT C_PACKAGE_NAME CHECK (TRIM(PACKAGE_NAME) <> ''),
    CONSTRAINT C_PACKAGE_RATE CHECK (RATE >= 0),
    CONSTRAINT CH_INH_PACKAGE CHECK (RATE_TYPE IN ('N', 'T'))
) COMMENT = 'An add-on package (e.g. drinks, Wi-Fi) charged per night or per trip';

CREATE TABLE ADH_BOOKING (
    BOOKING_ID                INT          NOT NULL AUTO_INCREMENT COMMENT 'Invoice ID',
    INVOICE_DATE              DATE         NOT NULL COMMENT 'Invoice date',
    STATEROOM_PRICE_PER_NIGHT DECIMAL(8,2) NOT NULL COMMENT 'Stateroom price per night',
    GROUP_ID                  INT          NOT NULL COMMENT 'Group ID',
    TRIP_ID                   INT          NOT NULL COMMENT 'Trip ID',
    STATEROOM_ID              INT          NOT NULL COMMENT 'Stateroom ID',
    CONSTRAINT ADH_BOOKING_PK PRIMARY KEY (BOOKING_ID),
    CONSTRAINT ADH_BOOKING_GROUP_FK FOREIGN KEY (GROUP_ID)
        REFERENCES ADH_GROUP (GROUP_ID),
    CONSTRAINT ADH_BOOKING_TRIP_FK FOREIGN KEY (TRIP_ID)
        REFERENCES ADH_TRIP (TRIP_ID),
    CONSTRAINT ADH_BOOKING_STATEROOM_FK FOREIGN KEY (STATEROOM_ID)
        REFERENCES ADH_STATEROOM (STATEROOM_ID),
    CONSTRAINT ADH_BOOKING_TRIP_STATEROOM_UK UNIQUE (TRIP_ID, STATEROOM_ID),
    CONSTRAINT C_BOOKING_PRICE CHECK (STATEROOM_PRICE_PER_NIGHT > 0)
) COMMENT = 'A group''s reservation of a stateroom on a trip; also the invoice';

CREATE TABLE ADH_PACKAGE_BOOKED (
    BOOKING_ID  INT NOT NULL COMMENT 'Booking id',
    CUSTOMER_ID INT NOT NULL COMMENT 'Customer ID',
    PACKAGE_ID  INT NOT NULL COMMENT 'Package ID',
    CONSTRAINT ADH_PACKAGE_BOOKED_PK PRIMARY KEY (BOOKING_ID, CUSTOMER_ID, PACKAGE_ID),
    CONSTRAINT ADH_PACKAGE_BOOKING_FK FOREIGN KEY (BOOKING_ID)
        REFERENCES ADH_BOOKING (BOOKING_ID),
    CONSTRAINT ADH_PACKAGE_CUSTOMER_FK FOREIGN KEY (CUSTOMER_ID)
        REFERENCES ADH_CUSTOMER (CUSTOMER_ID),
    CONSTRAINT ADH_PACKAGE_BOOKED_FK FOREIGN KEY (PACKAGE_ID)
        REFERENCES ADH_PACKAGE (PACKAGE_ID)
) COMMENT = 'Which customer on a booking bought which package';

CREATE TABLE ADH_TRANSACTION (
    TRANSACTION_ID INT           NOT NULL AUTO_INCREMENT COMMENT 'Transaction ID',
    PAYMENT_DATE   DATE          NOT NULL COMMENT 'Payment date',
    PAYMENT_AMOUNT DECIMAL(9,2)  NOT NULL DEFAULT 0 COMMENT 'Payment amount',
    PAYMENT_METHOD VARCHAR(30)   COLLATE utf8mb4_bin NOT NULL COMMENT 'Payment method: Credit or ACH',
    BOOKING_ID     INT           NOT NULL COMMENT 'Booking ID',
    CONSTRAINT ADH_TRANSACTION_PK PRIMARY KEY (TRANSACTION_ID),
    CONSTRAINT ADH_TRANSACTION_BOOKING_FK FOREIGN KEY (BOOKING_ID)
        REFERENCES ADH_BOOKING (BOOKING_ID),
    CONSTRAINT C_TRANSACTION_AMOUNT CHECK (PAYMENT_AMOUNT >= 0),
    CONSTRAINT C_TRANSACTION_METHOD CHECK (PAYMENT_METHOD IN ('Credit', 'ACH'))
) COMMENT = 'A payment toward a booking; a booking can be paid in several parts';
