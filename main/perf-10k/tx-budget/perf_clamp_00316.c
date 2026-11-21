/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00316(unsigned int count)
{
    const unsigned int limit = 151u;
    return count > limit ? limit : count;
}
