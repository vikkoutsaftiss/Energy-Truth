using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using System.Text;

namespace Infrastructure.DataAccess.Entities
{
    [Table("klant")]
    public class Customer
    {
        [Column("id")]
        public int Id { get; set; }
        [Column("email")]
        public string Email { get; set; }
        [Column("wachtwoord")]
        public string Password { get; set; }
        [Column("btw_nummer")]
        [MaxLength(20)]
        public string? VATNumber { get; set; }
        [Column("adres")]
        public string Address { get; set; }
        [Column("bedrijfsnaam")]
        public string? BusinessName { get; set; }
        [Column("klanttype")]
        public string? CustomerType { get; set; }
        [Column("email_verifieerd")]
        public bool? EmailConfirmed { get; set; }
    }
}
