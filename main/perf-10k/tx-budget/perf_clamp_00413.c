/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00413(unsigned int count)
{
    const unsigned int limit = 57u;
    return count > limit ? limit : count;
}
