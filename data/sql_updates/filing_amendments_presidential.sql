drop materialized view if exists ofec_presidential_paper_amendments_mv_tmp cascade;
create materialized view ofec_presidential_paper_amendments_mv_tmp as
with recursive oldest_filing_paper as (
  (
    SELECT cmte_id,
      rpt_yr,
      rpt_tp,
      amndt_ind,
      receipt_dt,
      file_num,
      prev_file_num,
      mst_rct_file_num,
      array[file_num]::numeric[] as amendment_chain,
      array[receipt_dt]::timestamp[] as date_chain,
      1 as depth,
      file_num as last
    FROM disclosure.nml_form_3p
    WHERE amndt_ind = 'N' and file_num < 0
  )
  union
  select
    f3p.cmte_id,
    f3p.rpt_yr,
    f3p.rpt_tp,
    f3p.amndt_ind,
    f3p.receipt_dt,
    f3p.file_num,
    f3p.prev_file_num,
    f3p.mst_rct_file_num,
    (oldest.amendment_chain || f3p.file_num)::numeric(7,0)[],
    (oldest.date_chain || f3p.receipt_dt)::timestamp[],
    oldest.depth + 1,
    oldest.amendment_chain[1]
  from oldest_filing_paper oldest, disclosure.nml_form_3p f3p
  where f3p.amndt_ind = 'A' and f3p.rpt_tp = oldest.rpt_tp and f3p.rpt_yr = oldest.rpt_yr and f3p.cmte_id = oldest.cmte_id and f3p.file_num < 0 and f3p.receipt_dt > date_chain[array_length(date_chain, 1)]
), longest_path as
  (SELECT b.*
   FROM oldest_filing_paper a LEFT OUTER JOIN oldest_filing_paper b ON a.file_num = b.file_num
   WHERE a.depth < b.depth
), filtered_longest_path as
   (select distinct old_f.* from oldest_filing_paper old_f, longest_path lp where old_f.date_chain <= lp.date_chain
  order by depth desc),
  paper_recent_filing as (
      SELECT a.*
      from filtered_longest_path a LEFT OUTER JOIN  filtered_longest_path b
        on a.cmte_id = b.cmte_id and a.last = b.last and a.depth < b.depth
        where b.cmte_id is null
  ),
    paper_filer_chain as(
      select flp.cmte_id,
      flp.rpt_yr,
      flp.rpt_tp,
      flp.amndt_ind,
      flp.receipt_dt,
      flp.file_num,
      flp.prev_file_num,
      prf.file_num as mst_rct_file_num,
      flp.amendment_chain
      from filtered_longest_path flp inner join paper_recent_filing prf on flp.cmte_id = prf.cmte_id
        and flp.last = prf.last)
    select row_number() over () as idx, * from paper_filer_chain;
;

create unique index on ofec_presidential_paper_amendments_mv_tmp(idx);
