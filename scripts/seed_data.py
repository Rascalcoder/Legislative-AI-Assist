"""
Seed competition law documents into Supabase.

Usage:
    python -m scripts.seed_data          # insert (skip existing)
    python -m scripts.seed_data --force  # delete existing + re-insert
"""
import asyncio
import logging
import sys
import time

# Add project root to path
sys.path.insert(0, ".")

from config import cfg
from services.document_service import chunk_text
from services.llm_client import embed_batch
from services import supabase_service as db

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# Seed documents — SK and EU competition law excerpts
# ============================================================

SEED_DOCUMENTS = [
    {
        "filename": "Zakon_187_2021_ochrana_hospodarskej_sutaze.txt",
        "source_id": "slov_lex_competition",
        "jurisdiction": "SK",
        "language": "sk",
        "document_type": "legislation",
        "content": (
            "Zakon c. 187/2021 Z.z. o ochrane hospodarskej sutaze\n\n"
            "Paragraf 4 - Dohody obmedzujuce sutaz\n"
            "Zakazane su dohody medzi podnikatelmi, rozhodnutia zdruzeni podnikatelov "
            "a zosulladene postupy, ktorych cielom alebo nasledkom je obmedzenie sutaze. "
            "Za dohody obmedzujuce sutaz sa povazuju najma dohody o priamom alebo nepriamom "
            "urceni cien tovarov, obmedzeni alebo kontrole vyroby, odbytu, technickeho rozvoja "
            "alebo investicii, rozdeleni trhu alebo zdrojov zasobovania, a uplatneni "
            "nerovnakych podmienok voci jednotlivym podnikatelom pri rovnakom plneni.\n\n"
            "Paragraf 5 - Vynimky zo zakazu\n"
            "Zakaz podla paragrafu 4 sa nevztahuje na dohody, ktore prispievaju k zlepseniu "
            "vyroby alebo distribucie tovarov alebo k podpore technickeho alebo hospodarskeho "
            "pokroku pri sucasnom poskytovani primeraneho podielu spotrebitelom na vyhodach "
            "z toho vyplyvajucich.\n\n"
            "Paragraf 8 - Zneuzitie dominantneho postavenia\n"
            "Zakazane je zneuzivanie dominantneho postavenia na relevantnom trhu. "
            "Za zneuzitie sa povazuje najma priame alebo nepriame vnucovanie neprimerane "
            "vysokych cien alebo inych neprimerane obchodnych podmienok, obmedzovanie "
            "vyroby, odbytu alebo technickeho rozvoja na ukor spotrebitelov, a uplatnenie "
            "nerovnakych podmienok pri rovnakom plneni voci jednotlivym podnikatelom.\n\n"
            "Paragraf 10 - Kontrola koncentracii\n"
            "Koncentracia podlieha kontrole uradu ak celkovy obrat podnikatelov za posledne "
            "uctovne obdobie presahuje v Slovenskej republike 46 000 000 eur a sucasne obrat "
            "kazdeho z aspon dvoch podnikatelov presahuje 14 000 000 eur."
        ),
    },
    {
        "filename": "Zakon_136_2001_ochrana_hospodarskej_sutaze_stary.txt",
        "source_id": "slov_lex_old",
        "jurisdiction": "SK",
        "language": "sk",
        "document_type": "legislation",
        "content": (
            "Zakon c. 136/2001 Z.z. o ochrane hospodarskej sutaze (stary zakon)\n\n"
            "Tento zakon upravuje ochranu hospodarskej sutaze na trhu vyrobkov, vykonov, "
            "prac a sluzieb proti jej obmedzovaniu, upravuje pravomoc a posobnost "
            "Protimonopolneho uradu Slovenskej republiky.\n\n"
            "Zakladne pojmy:\n"
            "Podnikatel je fyzicka osoba alebo pravnicka osoba, ktora sa zucastnuje na "
            "hospodarskej sutazi. Relevantny trh je trh tovarov, ktore su z hladiska ich "
            "charakteristiky, ceny a zamyslaneho pouzivania zamenitelne. Dominantne postavenie "
            "ma podnikatel alebo viaceri podnikatelia, ktori nie su vystaveni podstatnej sutazi "
            "na relevantnom trhu.\n\n"
            "Protimonopolny urad SR je ustredny organ statnej spravy pre ochranu hospodarskej "
            "sutaze. Urad rozhoduje vo veciach dohod obmedzujucich sutaz, zneuzitia "
            "dominantneho postavenia a kontroly koncentracii."
        ),
    },
    {
        "filename": "TFEU_Articles_101_102.txt",
        "source_id": "tfeu_101_102",
        "jurisdiction": "EU",
        "language": "en",
        "document_type": "treaty",
        "content": (
            "Treaty on the Functioning of the European Union (TFEU)\n\n"
            "Article 101\n"
            "1. The following shall be prohibited as incompatible with the internal market: "
            "all agreements between undertakings, decisions by associations of undertakings "
            "and concerted practices which may affect trade between Member States and which "
            "have as their object or effect the prevention, restriction or distortion of "
            "competition within the internal market, and in particular those which:\n"
            "(a) directly or indirectly fix purchase or selling prices or any other trading conditions;\n"
            "(b) limit or control production, markets, technical development, or investment;\n"
            "(c) share markets or sources of supply;\n"
            "(d) apply dissimilar conditions to equivalent transactions with other trading parties;\n"
            "(e) make the conclusion of contracts subject to acceptance of supplementary obligations.\n\n"
            "2. Any agreements or decisions prohibited pursuant to this Article shall be "
            "automatically void.\n\n"
            "3. The provisions of paragraph 1 may be declared inapplicable in the case of "
            "any agreement which contributes to improving the production or distribution of "
            "goods or to promoting technical or economic progress, while allowing consumers "
            "a fair share of the resulting benefit.\n\n"
            "Article 102\n"
            "Any abuse by one or more undertakings of a dominant position within the internal "
            "market or in a substantial part of it shall be prohibited as being incompatible "
            "with the internal market in so far as it may affect trade between Member States. "
            "Such abuse may, in particular, consist in:\n"
            "(a) directly or indirectly imposing unfair purchase or selling prices;\n"
            "(b) limiting production, markets or technical development to the prejudice of consumers;\n"
            "(c) applying dissimilar conditions to equivalent transactions;\n"
            "(d) making the conclusion of contracts subject to acceptance of supplementary obligations."
        ),
    },
    {
        "filename": "Regulation_1_2003_antitrust_enforcement.txt",
        "source_id": "regulation_1_2003",
        "jurisdiction": "EU",
        "language": "en",
        "document_type": "regulation",
        "content": (
            "Council Regulation (EC) No 1/2003 on the implementation of the rules on "
            "competition laid down in Articles 81 and 82 of the Treaty (now Articles 101 and 102 TFEU)\n\n"
            "Article 1 - Application of Articles 101 and 102\n"
            "Agreements, decisions and concerted practices caught by Article 101(1) which "
            "satisfy the conditions of Article 101(3) shall not be prohibited, no prior "
            "decision to that effect being required.\n\n"
            "Article 2 - Burden of proof\n"
            "The burden of proving an infringement of Article 101(1) or Article 102 shall "
            "rest on the party or the authority alleging the infringement. The undertaking "
            "claiming the benefit of Article 101(3) shall bear the burden of proving that "
            "the conditions are fulfilled.\n\n"
            "Article 3 - Relationship between Articles 101 and 102 and national competition laws\n"
            "Where the competition authorities of the Member States or national courts apply "
            "national competition law to agreements which may affect trade between Member States, "
            "they shall also apply Article 101.\n\n"
            "Article 5 - Powers of the competition authorities of the Member States\n"
            "The competition authorities of the Member States shall have the power to apply "
            "Articles 101 and 102 in individual cases.\n\n"
            "Article 23 - Fines\n"
            "The Commission may by decision impose fines on undertakings where, either "
            "intentionally or negligently, they infringe Article 101 or Article 102. "
            "For each undertaking participating in the infringement, the fine shall not "
            "exceed 10% of its total turnover in the preceding business year."
        ),
    },
    {
        "filename": "Regulation_139_2004_EU_Merger_Regulation.txt",
        "source_id": "eu_merger_regulation",
        "jurisdiction": "EU",
        "language": "en",
        "document_type": "regulation",
        "content": (
            "Council Regulation (EC) No 139/2004 on the control of concentrations between "
            "undertakings (the EU Merger Regulation)\n\n"
            "Article 1 - Scope\n"
            "This Regulation shall apply to all concentrations with a Community dimension. "
            "A concentration has a Community dimension where the combined aggregate worldwide "
            "turnover of all the undertakings concerned is more than EUR 5 000 million, and "
            "the aggregate Community-wide turnover of each of at least two of the undertakings "
            "concerned is more than EUR 250 million.\n\n"
            "Article 2 - Appraisal of concentrations\n"
            "Concentrations which would significantly impede effective competition, in the "
            "common market or in a substantial part of it, in particular as a result of the "
            "creation or strengthening of a dominant position, shall be declared incompatible "
            "with the common market.\n\n"
            "Article 3 - Definition of concentration\n"
            "A concentration shall be deemed to arise where a change of control on a lasting "
            "basis results from the merger of two or more previously independent undertakings, "
            "or the acquisition by one or more persons or undertakings of direct or indirect "
            "control of the whole or parts of one or more other undertakings.\n\n"
            "Article 7 - Suspension of concentrations\n"
            "A concentration with a Community dimension shall not be implemented before "
            "notification or until it has been declared compatible with the common market."
        ),
    },
    {
        "filename": "PMU_rozhodnutie_kartely_priklad.txt",
        "source_id": "pmu_decisions",
        "jurisdiction": "SK",
        "language": "sk",
        "document_type": "authority_decisions",
        "content": (
            "Protimonopolny urad Slovenskej republiky - Rozhodnutie\n"
            "Cislo konania: 2023/KA/1/1/001\n\n"
            "Protimonopolny urad Slovenskej republiky rozhodol, ze ucastnici konania "
            "uzavreli dohodu obmedzujucu sutaz podla paragrafu 4 ods. 1 zakona c. 187/2021 Z.z. "
            "o ochrane hospodarskej sutaze a clanku 101 Zmluvy o fungovani Europskej unie.\n\n"
            "Podnikatelia sa dohodli na koordinacii cenovych ponuk v ramci verejneho "
            "obstaravania, cim doslo k obmedzeniu sutaze na relevantnom trhu.\n\n"
            "Urad ulozil pokutu vo vyske 3% z obratu za predchadzajuce uctovne obdobie. "
            "Pri urceni vysky pokuty urad zohladnil zavaznost a trvanie porusenia, "
            "rozsah poskodeneneho trhu a mieru ucastt jednotlivych podnikatelov na poruseni.\n\n"
            "Proti tomuto rozhodnutiu je mozne podat rozklad."
        ),
    },
    {
        "filename": "EU_Commission_Decision_example.txt",
        "source_id": "eu_commission_decisions",
        "jurisdiction": "EU",
        "language": "en",
        "document_type": "authority_decisions",
        "content": (
            "European Commission - Competition Decision\n"
            "Case COMP/AT.00001\n\n"
            "The European Commission has found that the undertakings concerned have "
            "infringed Article 101 of the Treaty on the Functioning of the European Union "
            "by participating in arrangements to coordinate pricing and allocate customers "
            "in the European Economic Area.\n\n"
            "The Commission considers that such arrangements constitute a restriction of "
            "competition by object within the meaning of Article 101(1) TFEU. The agreements "
            "had an appreciable effect on trade between Member States.\n\n"
            "The Commission has imposed fines calculated on the basis of the Guidelines on "
            "the method of setting fines (2006/C 210/02). The basic amount was determined "
            "by reference to the value of sales and the duration of the infringement. "
            "Aggravating and mitigating circumstances were taken into account.\n\n"
            "The undertakings may appeal this decision before the General Court of the "
            "European Union within two months of notification."
        ),
    },
]


def _check_existing(source_id: str) -> bool:
    """Check if a document with this source_id already exists."""
    result = (
        db._get_client()
        .table("documents")
        .select("id")
        .eq("source_id", source_id)
        .execute()
    )
    return len(result.data) > 0


def _delete_by_source_id(source_id: str):
    """Delete document (and cascaded chunks) by source_id."""
    db._get_client().table("documents").delete().eq("source_id", source_id).execute()
    logger.info(f"  Deleted existing: {source_id}")


async def seed_document(doc: dict) -> int:
    """Seed a single document. Returns chunk count."""
    # Insert document record
    doc_id = db.insert_document(
        filename=doc["filename"],
        document_type=doc["document_type"],
        language=doc["language"],
        size_bytes=len(doc["content"].encode("utf-8")),
        jurisdiction=doc["jurisdiction"],
        source_id=doc["source_id"],
    )

    # Chunk
    chunks = chunk_text(doc["content"])
    logger.info(f"  {len(chunks)} chunks created")

    # Embed
    embeddings = await embed_batch(chunks)
    logger.info(f"  {len(embeddings)} embeddings generated")

    # Insert chunks
    chunk_records = []
    for i, (text, emb) in enumerate(zip(chunks, embeddings)):
        chunk_records.append({
            "document_id": doc_id,
            "chunk_index": i,
            "content": text,
            "embedding": emb,
            "language": doc["language"],
            "jurisdiction": doc["jurisdiction"],
            "metadata": {
                "filename": doc["filename"],
                "document_type": doc["document_type"],
                "source_id": doc["source_id"],
            },
        })

    db.insert_chunks(chunk_records)

    # Update status
    db.update_document_status(doc_id, "processed", len(chunks))

    return len(chunks)


async def main():
    force = "--force" in sys.argv

    logger.info("=" * 60)
    logger.info("Legislative AI Assist - Seed Data")
    logger.info(f"Mode: {'FORCE (delete + re-insert)' if force else 'SKIP existing'}")
    logger.info(f"Documents: {len(SEED_DOCUMENTS)}")
    logger.info("=" * 60)

    start = time.time()
    total_chunks = 0
    inserted = 0
    skipped = 0

    for doc in SEED_DOCUMENTS:
        logger.info(f"\n[{doc['jurisdiction']}] {doc['filename']}")

        exists = _check_existing(doc["source_id"])

        if exists and not force:
            logger.info("  SKIP (already exists)")
            skipped += 1
            continue

        if exists and force:
            _delete_by_source_id(doc["source_id"])

        chunks = await seed_document(doc)
        total_chunks += chunks
        inserted += 1
        logger.info(f"  OK ({chunks} chunks)")

    elapsed = time.time() - start

    logger.info("\n" + "=" * 60)
    logger.info(f"Done in {elapsed:.1f}s")
    logger.info(f"Inserted: {inserted} documents, {total_chunks} chunks")
    logger.info(f"Skipped: {skipped} (already existed)")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
