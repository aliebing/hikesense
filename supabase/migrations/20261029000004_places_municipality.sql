-- Gemeinden (admin_level=8) als Ortsart, damit "Feldberg (Schwarzwald)" auflösbar ist (R24).
alter table places drop constraint places_kind_check;
alter table places add constraint places_kind_check
  check (kind in ('town', 'village', 'hamlet', 'peak', 'lake', 'municipality'));
