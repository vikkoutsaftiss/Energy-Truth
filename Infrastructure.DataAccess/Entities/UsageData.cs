using System.ComponentModel.DataAnnotations.Schema;
using System.ComponentModel.DataAnnotations;

namespace Infrastructure.DataAccess.Entities
{
    [Table("Verbruiksdata")]
    public class UsageData
    {
        [Column("ID")]
        public int Id { get; set; }
        [Column("ImportBatchID")]
        public int ImportBatchId { get; set; }
        [Column("Gebouw_ID")]
        public int BuildingId { get; set; }
        [Column("MeetDatum")]
        public DateTime UsageMoment {  get; set; }
        [Column("Bron_Data")]
        [MaxLength(255)]
        public string SourceData   { get; set; }
        [Column("Stroom_Gekocht_Net_kWh")]
        public decimal? KWhBought { get; set; }
        [Column("Stroom_Verkocht_Net_kWh")]
        public decimal? KWhSold { get; set; }
    }
}
