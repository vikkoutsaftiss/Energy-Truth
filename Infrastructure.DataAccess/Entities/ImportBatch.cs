using Energy_Truth.Shared.DTO_s;
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations.Schema;
using System.Text;

namespace Infrastructure.DataAccess.Entities
{
    [Table("ImportBatch")]
    public class ImportBatch
    {
        [Column("ID")]
        public int ImportBatchId { get; set; }
        [Column("GebouwID")]
        public int BuildingId { get; set; }
        [Column("ImportedAt")]
        public DateTime ImportedAt { get; set; }
        [Column("Status")]
        public string Status { get; set; }
        [Column("Eigen_Batterij")]
        public string? CustomBattery { get; set; }

        public UsageData UsageData { get; set; }
    }
}
