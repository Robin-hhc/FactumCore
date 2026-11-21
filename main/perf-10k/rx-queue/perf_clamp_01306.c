/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01306(unsigned int count)
{
    const unsigned int limit = 49u;
    return count > limit ? limit : count;
}
