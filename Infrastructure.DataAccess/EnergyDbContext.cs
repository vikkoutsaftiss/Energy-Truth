using Microsoft.EntityFrameworkCore;
using System;
using System.Collections.Generic;
using System.Text;

namespace Infrastructure.DataAccess
{
    public class EnergyDbContext : DbContext
    {
        public EnergyDbContext(DbContextOptions<EnergyDbContext> options) : base(options)
        {
        }
        public DbSet<UsageData> UsageData { get; set; }
        public DbSet<ImportBatch> ImportBatches { get; set; }
    }
}
