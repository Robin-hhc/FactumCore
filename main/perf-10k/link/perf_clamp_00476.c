/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00476(unsigned int count)
{
    const unsigned int limit = 132u;
    return count > limit ? limit : count;
}
