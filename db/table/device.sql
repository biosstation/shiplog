/* Deployable device

This is a self-referencing table where devices with multiple types are have a parent
*/
create table device
(
    DID int unsigned not null auto_increment unique primary key,
    PARENT_DID int unsigned,
    name varchar(25) unique not null,
    foreign key(PARENT_DID) references device(DID)
) engine=InnoDB default charset=utf8;
