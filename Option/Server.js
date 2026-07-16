const express = require("express");
const cors = require("cors");

const { NseIndia } = require("stock-nse-india");

const app = express();

app.use(cors());

const nse = new NseIndia();

// Simple in-memory cache: { [symbol]: { data, ts } }
// Keeps the same NSE snapshot for 60 s so insert + validate always compare
// the identical data set and don't diverge on live-updating fields (turnover, OI).
const CACHE_TTL_MS = 60_000;
const optionsCache = {};
const serverless = require("serverless-http");

// =====================================
// OPTIONS CHAIN API
// =====================================
app.get("/options/:symbol", async (req, res) => {

    try {

        const symbol = req.params.symbol.toUpperCase();

        // =============================
        // CACHE LOOKUP
        // =============================
        const now = Date.now();
        if (optionsCache[symbol] && (now - optionsCache[symbol].ts) < CACHE_TTL_MS) {
            return res.json(optionsCache[symbol].response);
        }

        let data;

        // =============================
        // INDEX OPTIONS
        // =============================
        if (
            symbol === "NIFTY" ||
            symbol === "BANKNIFTY" ||
            symbol === "FINNIFTY"
        ) {

            data =
                await nse.getIndexOptionChain(symbol);

        }

        // =============================
        // EQUITY OPTIONS
        // =============================
        else {

            data =
                await nse.getEquityOptionChain(symbol);
        }

        const rows = [];

        const optionData = data.data;

        optionData.forEach((item) => {

            // =============================
            // ONLY OPTION CONTRACTS
            // =============================
            if (item.instrumentType !== "OPTSTK") {
                return;
            }

            rows.push({

                symbol: item.underlying,

                expiry: item.expiryDate,

                strike: parseFloat(item.strikePrice),

                type:
                    item.optionType === "CE"
                        ? "CALL"
                        : "PUT",

                last_price: item.lastPrice,

                open: item.openPrice,

                high: item.highPrice,

                low: item.lowPrice,

                close: item.closePrice,

                previous_close: item.prevClose,

                change: item.change,

                change_percent: item.pchange,

                volume: item.totalTradedVolume,

                turnover: item.totalTurnover,

                open_interest: item.openInterest,

                change_in_oi:
                    item.changeinOpenInterest,

                oi_change_percent:
                    item.pchangeinOpenInterest,

                underlying_value:
                    item.underlyingValue,

                identifier: item.identifier
            });
        });

        // =============================
        // SORT BY STRIKE
        // =============================
        rows.sort((a, b) => a.strike - b.strike);

        const response = {
            success: true,
            symbol,
            total_rows: rows.length,
            data: rows
        };

        // Store in cache for CACHE_TTL_MS so insert + validate get identical data
        optionsCache[symbol] = { response, ts: Date.now() };

        res.json(response);

    } catch (err) {

        console.error(err);

        res.status(500).json({

            success: false,

            error: err.message
        });
    }
});


// =====================================
// HEALTH CHECK
// =====================================
app.get("/", (req, res) => {

    res.json({
        success: true,
        message: "Options service running"
    });
});


if (process.env.AWS_LAMBDA_FUNCTION_NAME) {
    // Running inside Lambda — export the handler, don't bind a port
    module.exports.handler = serverless(app);
} else {
    // Running locally — behave exactly like before
    const PORT = 5001;
    app.listen(PORT, () => {
        console.log(`Options service running on port ${PORT}`);
    });
}

app.get("/test", async (req, res) => {
    try {
        const data = await nse.getEquityDetails("RELIANCE");

        res.json({
            success: true,
            data
        });
    } catch (err) {
        console.error("FULL ERROR:", err);
        console.error("STATUS:", err.response?.status);
        console.error("HEADERS:", err.response?.headers);
        console.error("BODY:", err.response?.data);

        res.status(500).json({
            success: false,
            message: err.message
        });
    }
});