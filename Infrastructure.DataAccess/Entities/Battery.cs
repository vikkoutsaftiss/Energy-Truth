using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations.Schema;
using System.Text;

namespace Infrastructure.DataAccess.Entities
{
    [Table("Markt_Product")]
    public class Battery
    {
        [Column("ID")]
        public int Id { get; set; }
        [Column("ProductNaam")]
        public string ProductName { get; set; }
        [Column("Categorie_Batterij")]
        public string ProductCategory { get; set; }
        [Column("Aanschafprijs")]
        public decimal Price { get; set; }
        [Column("Capaciteit_kWh")]
        public decimal CapacityKWh {  get; set; }
        [Column("Gegarandeerde_laadcycli")]
        public int GuaranteedCycles { get; set; }
        [Column("garantiejaren")]
        public int WarrantyPeriodYears { get; set; }
        [Column("Max_Laden_kW")]
        public decimal MaxChargePower { get; set; }
        [Column("Max_Ontladen_kW")]
        public decimal MaxDischargePower { get; set; }
        [Column("Bruikbare_CapaciteitkW")]
        public decimal UsableCapacityKWh { get; set; }
        [Column("Round_Trip_Efficiency")]
        public decimal RoundTripEfficiency { get; set; }
        [Column("Installatiekosten_EUR")]
        public decimal? InstallationCost { get; set; }
        [Column("Chemie")]
        public string Chemistry { get; set; }



    }
}
