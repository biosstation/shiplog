drop procedure if exists insert_device;

/* Insert a device into the database
No records will be inserted if a parent device ID does not exist.
Pass in null if a device does not have a parent ID
*/
create procedure insert_device
(
    in p_name char(25),
    in p_parent_did int unsigned
)
begin

    insert into device(name, parent_did)
	select p_name,
        p_parent_did
    from dual
	where exists (
		select *
		from device
		where DID = p_parent_did
    ) or p_parent_did is null;
	select last_insert_id();

end
