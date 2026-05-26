using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations.Schema;
using System.Text;

namespace Infrastructure.DataAccess
{
    public class ImportBatch
    {
        [Column("ImportBatchID")]
        public int ImportBatchId { get; set; }
        [Column("GebouwID")]
        public int BuildingId { get; set; }
        [Column("ImportedAt")]
        public DateTime ImportedAt { get; set; }
    }
}
