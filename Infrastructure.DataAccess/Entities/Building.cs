using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using System.Text;

namespace Infrastructure.DataAccess.Entities
{
    [Table("Gebouw")]
    public class Building
    {
        [Column("ID")]
        public int Id { get; set; }
        [Column("Klant_ID")]
        public int CustomerId { get; set; }
        [Column("Postcode")]
        [MaxLength(10)]
        public string PostalCode { get; set; }
        [Column("Bouwjaar")]
        public int? ConstructionYear { get; set; }
        [Column("ISTEnergyLabel")]
        public string? ISTEnergyLabel { get; set; }
    }
}
