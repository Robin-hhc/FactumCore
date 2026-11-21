/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08844(unsigned int count)
{
    const unsigned int limit = 209u;
    return count > limit ? limit : count;
}
