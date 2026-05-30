using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using System.Text;

namespace Infrastructure.DataAccess.Entities
{
    [Table("Klant")]
    public class Customer
    {
        [Column("ID")]
        public int Id { get; set; }
        [Column("Email")]
        public string Email { get; set; }
        [Column("Wachtwoord_Hash")]
        public string Password { get; set; }
        [Column("BTW_Nummer")]
        [MaxLength(20)]
        public string? VATNumber { get; set; }
        [Column("Adres")]
        public string Address { get; set; }
        [Column("Bedrijfsnaam")]
        public string? BusinessName { get; set; }
        [Column("Klanttype")]
        public string? CustomerType { get; set; }
        [Column("Email_verifieerd")]
        public bool? EmailConfirmed { get; set; }
    }
}
