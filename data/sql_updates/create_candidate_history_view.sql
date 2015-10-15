drop materialized view if exists ofec_candidate_history_mv_tmp cascade;
create materialized view ofec_candidate_history_mv_tmp as
with
    years as (
        select
            cand_id,
            array_agg(cand_election_yr)::int[] as election_years,
            array_agg(cand_office_district)::text[] as election_districts
        from cand_valid_fec_yr
        group by cand_id
    ),
    active_agg as (
        select
            cand_id,
            max(cand_election_yr) as active_through
        from cand_valid_fec_yr
        group by cand_id
    ),
    cycles as (
        select
            cand_sk,
            generate_series(
                min(get_cycle(election_yr)),
                max(get_cycle(election_yr)),
                2
            ) as cycle
        from dimcandproperties
        where form_tp != 'F2Z'
        group by cand_sk
    ),
    cycle_agg as (
        select
            cand_sk,
            array_agg(cycles.cycle)::int[] as cycles,
            max(cycles.cycle) as max_cycle
        from cycles
        group by cand_sk
    ),
    non_ballot_filers as (
        select distinct cand_sk
        from dimcandproperties
        where form_tp != 'F2Z'
    )
select distinct on (dcp.cand_sk, cycle)
    row_number() over () as idx,
    cycles.cycle as two_year_period,
    dcp.candproperties_sk as properties_key,
    dcp.cand_sk as candidate_key,
    dcp.cand_id as candidate_id,
    dcp.cand_nm as name,
    dcp.expire_date as expire_date,
    dcp.load_date as load_date,
    dcp.form_tp as form_type,
    dcp.cand_st as address_state,
    dcp.cand_city as address_city,
    dcp.cand_st1 as address_street_1,
    dcp.cand_st2 as address_street_2,
    dcp.cand_st2 as address_street,
    dcp.cand_zip as address_zip,
    dcp.cand_ici_cd as incumbent_challenge,
    expand_candidate_incumbent(dcp.cand_ici_cd) as incumbent_challenge_full,
    dcp.cand_status_cd as candidate_status,
    dcp.cand_status_desc as candidate_status_full,
    dsi.cand_inactive_flg as candidate_inactive,
    fec_yr.cand_office as office,
    expand_office(fec_yr.cand_office) as office_full,
    fec_yr.cand_office_st as state,
    fec_yr.cand_office_district as district,
    fec_yr.cand_office_district::int as district_number,
    fec_yr.cand_pty_affiliation as party,
    clean_party(dp.party_affiliation_desc) as party_full,
    cycle_agg.cycles,
    years.election_years,
    years.election_districts,
    active_agg.active_through
from dimcandproperties dcp
left join years using (cand_id)
left join active_agg using (cand_id)
left join cycle_agg on dcp.cand_sk = cycle_agg.cand_sk
left join cycles on dcp.cand_sk = cycles.cand_sk and dcp.election_yr <= cycles.cycle
left join dimcandstatusici dsi on dcp.cand_sk = dsi.cand_sk and dsi.election_yr <= cycles.cycle
inner join non_ballot_filers nbf on dcp.cand_sk = nbf.cand_sk
inner join cand_valid_fec_yr fec_yr on dcp.cand_id = fec_yr.cand_id and fec_yr.fec_election_yr <= cycles.cycle
inner join dimparty dp on fec_yr.cand_pty_affiliation = dp.party_affiliation
where max_cycle >= :START_YEAR
order by
    dcp.cand_sk,
    cycle desc,
    dcp.election_yr desc,
    dsi.election_yr desc,
    fec_yr.fec_election_yr desc,
    dcp.form_sk desc
;

create unique index on ofec_candidate_history_mv_tmp(idx);

create index on ofec_candidate_history_mv_tmp(candidate_key);
create index on ofec_candidate_history_mv_tmp(candidate_id);
create index on ofec_candidate_history_mv_tmp(two_year_period);
create index on ofec_candidate_history_mv_tmp(office);
create index on ofec_candidate_history_mv_tmp(state);
create index on ofec_candidate_history_mv_tmp(district);
create index on ofec_candidate_history_mv_tmp(district_number);


drop materialized view if exists ofec_candidate_detail_mv_tmp;
create materialized view ofec_candidate_detail_mv_tmp as
select distinct on (candidate_id) * from ofec_candidate_history_mv_tmp
order by candidate_id, two_year_period desc
;

create unique index on ofec_candidate_detail_mv_tmp(idx);

create index on ofec_candidate_detail_mv_tmp(name);
create index on ofec_candidate_detail_mv_tmp(party);
create index on ofec_candidate_detail_mv_tmp(state);
create index on ofec_candidate_detail_mv_tmp(office);
create index on ofec_candidate_detail_mv_tmp(district);
create index on ofec_candidate_detail_mv_tmp(load_date);
create index on ofec_candidate_detail_mv_tmp(party_full);
create index on ofec_candidate_detail_mv_tmp(expire_date);
create index on ofec_candidate_detail_mv_tmp(office_full);
create index on ofec_candidate_detail_mv_tmp(candidate_id);
create index on ofec_candidate_detail_mv_tmp(candidate_key);
create index on ofec_candidate_detail_mv_tmp(candidate_status);
create index on ofec_candidate_detail_mv_tmp(incumbent_challenge);

create index on ofec_candidate_detail_mv_tmp using gin (cycles);
create index on ofec_candidate_detail_mv_tmp using gin (election_years);

drop table if exists dimcand_fulltext;
drop materialized view if exists ofec_candidate_fulltext_mv_tmp;
create materialized view ofec_candidate_fulltext_mv_tmp as
select distinct on (candidate_id)
    row_number() over () as idx,
    candidate_id as id,
    name,
    office as office_sought,
    case
        when name is not null then
            setweight(to_tsvector(name), 'A') ||
            setweight(to_tsvector(candidate_id), 'B')
        else null::tsvector
    end
as fulltxt
from ofec_candidate_detail_mv_tmp
;

create unique index on ofec_candidate_fulltext_mv_tmp(idx);
create index on ofec_candidate_fulltext_mv_tmp using gin(fulltxt);
