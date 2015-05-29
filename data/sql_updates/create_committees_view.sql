drop view if exists ofec_committees_vw;
drop materialized view if exists ofec_committees_mv_tmp;
create materialized view ofec_committees_mv_tmp as
select distinct on (dcp.cmte_sk)
    row_number() over () as idx,
    dcp.cmte_sk as committee_key,
    dcp.cmte_id as committee_id,
    dd.cmte_dsgn as designation,
    expand_committee_designation(dd.cmte_dsgn) as designation_full,
    dd.cmte_tp as committee_type,
    expand_committee_type(dd.cmte_tp) as committee_type_full,
    cp_most_recent.cmte_treasurer_nm as treasurer_name,
    cp_most_recent.org_tp as organization_type,
    expand_organization_type(cp_most_recent.org_tp) as organization_type_full,
    cp_most_recent.cmte_st as state,
    cp_most_recent.expire_date as expire_date,
    cp_most_recent.cand_pty_affiliation as party,
    cp_most_recent.receipt_dt as last_file_date,
    cp_original.receipt_dt as first_file_date,
    clean_party(p.party_affiliation_desc) as party_full,
    cp_most_recent.cmte_nm as name,
    candidates.candidate_ids,
    cp_agg.cycles
from dimcmteproperties dcp
    left join (
        select distinct on (cmte_sk) * from dimcmtetpdsgn
            order by cmte_sk, receipt_date desc
    ) dd using (cmte_sk)
    -- do a DISTINCT ON subselect to get the most recent properties for a committee
    left join (
        select distinct on (cmte_sk) * from dimcmteproperties
            order by cmte_sk, receipt_dt desc
    ) cp_most_recent using (cmte_sk)
    left join(
        select cmte_sk, min(receipt_dt) receipt_dt from dimcmteproperties
            where form_tp = 'F1'
            group by cmte_sk
    ) cp_original using (cmte_sk)
    -- Aggregate election cycles from dimcmteproperties.rpt_yr
    left join (
        select
            cmte_sk,
            array_agg(distinct(rpt_yr + rpt_yr % 2))::int[] as cycles
        from (
            select cmte_sk, rpt_yr from factpacsandparties_f3x
            union
            select cmte_sk, rpt_yr from factpresidential_f3p
            union
            select cmte_sk, rpt_yr from facthousesenate_f3
        ) years
        where rpt_yr >= :START_YEAR
        group by cmte_sk
    ) cp_agg using (cmte_sk)
    left join dimparty p on cp_most_recent.cand_pty_affiliation = p.party_affiliation
    left join (
        select
            cmte_sk,
            array_agg(distinct cand_id)::text[] as candidate_ids
        from dimlinkages dl
        group by cmte_sk
    ) candidates on candidates.cmte_sk = dcp.cmte_sk
    -- Committee must have > 0 cycles after START_YEAR
    where array_length(cp_agg.cycles, 1) > 0
;

create unique index on ofec_committees_mv_tmp(idx);

create index on ofec_committees_mv_tmp(party);
create index on ofec_committees_mv_tmp(state);
create index on ofec_committees_mv_tmp(designation);
create index on ofec_committees_mv_tmp(expire_date);
create index on ofec_committees_mv_tmp(committee_id);
create index on ofec_committees_mv_tmp(committee_key);
create index on ofec_committees_mv_tmp(candidate_ids);
create index on ofec_committees_mv_tmp(committee_type);
create index on ofec_committees_mv_tmp(organization_type);

create index on ofec_committees_mv_tmp using gin (cycles);
