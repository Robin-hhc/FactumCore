/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02347(unsigned int count)
{
    const unsigned int limit = 67u;
    return count > limit ? limit : count;
}
