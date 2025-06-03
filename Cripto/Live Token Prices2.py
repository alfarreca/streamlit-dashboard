# -- Institutional Adoption Data --
institutional_adoption = [
    {
        "Institution": "Franklin Templeton",
        "Project/Token": "BENJI",
        "Initiative": "Tokenized US Govt. Money Fund (Stellar/Polygon)",
        "Summary": "First major asset manager to issue a regulated US fund as blockchain tokens."
    },
    {
        "Institution": "BlackRock",
        "Project/Token": "ONDO (partner)",
        "Initiative": "Tokenized Treasuries & Partnerships",
        "Summary": "Partners with Ondo to bring tokenized treasuries to institutions and DeFi."
    },
    {
        "Institution": "Ondo Finance",
        "Project/Token": "ONDO",
        "Initiative": "Tokenized Treasuries",
        "Summary": "Institutional partnerships with BlackRock, Morgan Stanley, and others."
    },
    {
        "Institution": "Backed Finance",
        "Project/Token": "bCSPX",
        "Initiative": "Tokenized ETFs/Stocks",
        "Summary": "Swiss-regulated tokenization of ETFs like iShares S&P 500."
    },
    {
        "Institution": "Maple Finance",
        "Project/Token": "MPL",
        "Initiative": "On-chain Institutional Lending",
        "Summary": "Lends to hedge funds, market makers, and now RWA borrowers."
    },
    {
        "Institution": "Centrifuge",
        "Project/Token": "CFG",
        "Initiative": "RWA Lending Pools",
        "Summary": "Works with fintechs and institutions to onboard real-world assets."
    },
    {
        "Institution": "Aave/Maker/Compound/Synthetix/Curve",
        "Project/Token": "AAVE, MKR, COMP, SNX, CRV",
        "Initiative": "DeFi Blue Chip RWA Integration",
        "Summary": "Protocols integrating RWA as collateral or lending assets."
    },
    {
        "Institution": "Polymesh",
        "Project/Token": "POLYX",
        "Initiative": "Regulated Digital Securities",
        "Summary": "Adopted by broker-dealers and banks for compliant digital assets."
    },
]
import pandas as pd  # (if not already imported)
institutional_df = pd.DataFrame(institutional_adoption)
