/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04483(unsigned int count)
{
    const unsigned int limit = 25u;
    return count > limit ? limit : count;
}
