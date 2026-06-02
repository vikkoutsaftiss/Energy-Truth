using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Text;

namespace Energy_Truth.Shared.DTO_s
{
    public class UsageDataDTO
    {
        public int BuildingId { get; set; }
        public DateTime UsageMoment { get; set; }
        public string SourceData { get; set; }
        public decimal? KWhBought { get; set; }
        public decimal? KWhSold { get; set; }

    }
}
